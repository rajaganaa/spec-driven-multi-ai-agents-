"""
hub/tools/tools.py — Part B: Tools Layer
==========================================

All tool functions specialist agents use to act on a project.

SAFETY MODEL
------------
Every operation is restricted to:

    workspace/projects/<project_id>/

No tool can read, write, list, search, or execute anything outside that
directory — not via absolute paths, not via `..` traversal, not via a
symlink that resolves elsewhere. See `_safe_path()` / `PathSandboxError`.

A second, separate sandbox exists for `specs/` (read_spec_file /
write_spec_file — see `_safe_specs_path()`), used only by the planning
agents in hub/agents/ (Orchestrator, Feature Lead). specs/ is hub-level
shared memory, not per-project source code, so it lives outside
workspace/projects/<project_id>/ entirely; specialists never use these.

`run_terminal` additionally enforces a command allowlist:
  - Unknown commands               -> blocked outright
  - Always-dangerous commands      -> blocked outright (sudo, ssh, dd, ...)
  - Sensitive-but-useful commands  -> require `approved=True` (rm, curl,
    wget, chmod, pip/npm install, git push, git reset --hard, ...)
  - Everything else on the allowlist runs freely (python, pytest, git
    status/commit, node, ls, cat, ...)

If Docker is available, commands run inside a throwaway container with
the project directory bind-mounted — this is the intended production
mode ("Sandbox execution" principle). If Docker is not available,
commands fall back to a local subprocess still confined to the
project's `cwd`, with `sandbox_mode` reported as "local-fallback" in the
result so callers know the isolation is weaker.

RETURN CONTRACT
---------------
Every public tool function returns a plain JSON-serializable dict:

    {"ok": True,  "error": None, ...data...}
    {"ok": False, "error": "<message>", ...partial data...}

Tools never raise for expected failure modes (missing file, blocked
command, sandbox violation) — they return ok=False so an LLM agent can
read the `error` field and decide what to do next. Tools may still raise
for genuine programmer errors (e.g. calling with wrong types).

USAGE
-----
Module-level functions all take `project_id` explicitly and are easiest
to unit test:

    >>> write_file("demo", "src/app.py", "print('hi')")
    >>> read_file("demo", "src/app.py")

For wiring into Google ADK `FunctionTool`s for one project at a time,
use `ProjectTools`, which binds `project_id` once and exposes the exact
signatures listed in the original tool spec (`read_file(path)`,
`write_file(path, content)`, etc.):

    >>> tools = ProjectTools("demo")
    >>> tools.read_file("src/app.py")
    >>> tools.run_terminal("pytest -q")
"""

from __future__ import annotations

import functools
import re
import shlex
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional

# ── Paths ─────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent.parent  # .../my-agent-hub
WORKSPACE_ROOT = (ROOT / "workspace" / "projects").resolve()
WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)

DEFAULT_DOCKER_IMAGE = "python:3.11-slim"
DEFAULT_TIMEOUT_SECONDS = 120
MAX_READ_BYTES = 1_000_000
MAX_SEARCH_RESULTS = 200
MAX_DIR_ENTRIES = 1000

# Directories never walked by list_dir / search_code (noise, not useful context)
_SKIP_DIR_NAMES = {".git", "node_modules", "__pycache__", ".venv", "venv", ".mypy_cache", ".pytest_cache"}


class PathSandboxError(Exception):
    """Raised when a path or project_id would resolve outside the sandbox."""


# ── Sandbox helpers ───────────────────────────────────────────────────────

def _project_root(project_id: str) -> Path:
    """Resolve (and create) workspace/projects/<project_id>/, refusing
    any project_id that isn't a single, simple directory name."""
    if not project_id or not isinstance(project_id, str):
        raise PathSandboxError(f"Invalid project_id: {project_id!r}")
    if any(sep in project_id for sep in ("/", "\\")) or project_id in (".", ".."):
        raise PathSandboxError(f"Invalid project_id: {project_id!r}")

    root = (WORKSPACE_ROOT / project_id).resolve()
    if root != WORKSPACE_ROOT and WORKSPACE_ROOT not in root.parents:
        raise PathSandboxError(f"project_id escapes workspace root: {project_id!r}")

    root.mkdir(parents=True, exist_ok=True)
    return root


def _looks_absolute(rel_path: str) -> bool:
    """True if rel_path is an absolute path on ANY platform.

    Path.is_absolute() only recognizes the *current* platform's syntax.
    On Windows, Path('/etc/passwd').is_absolute() is False (Windows
    absolute paths need a drive letter, e.g. 'C:/...'), so a POSIX-style
    absolute path silently slips past an is_absolute()-only check. We
    also reject a leading slash/backslash and a drive-letter prefix so
    this behaves identically regardless of host OS.
    """
    if not rel_path:
        return False
    if Path(rel_path).is_absolute():
        return True
    return bool(rel_path.startswith(("/", "\\")) or re.match(r"^[a-zA-Z]:[\\/]", rel_path))


def _safe_path(project_id: str, rel_path: str) -> Path:
    """Resolve rel_path against the project's sandbox root. Rejects
    absolute paths and any traversal (including via symlinks) that
    would land outside the sandbox."""
    proj_root = _project_root(project_id).resolve()

    if rel_path in (None, ""):
        rel_path = "."

    if _looks_absolute(rel_path):
        raise PathSandboxError(f"Absolute paths are not allowed: {rel_path!r}")

    candidate = Path(rel_path)
    resolved = (proj_root / candidate).resolve()

    try:
        resolved.relative_to(proj_root)
    except ValueError:
        raise PathSandboxError(f"Path '{rel_path}' resolves outside sandbox for project '{project_id}'")

    return resolved


# ── Result helpers ────────────────────────────────────────────────────────

def _ok(**kwargs) -> dict:
    return {"ok": True, "error": None, **kwargs}


def _err(message: str, **kwargs) -> dict:
    return {"ok": False, "error": message, **kwargs}


# ── read_file ─────────────────────────────────────────────────────────────

def read_file(project_id: str, path: str, max_bytes: int = MAX_READ_BYTES) -> dict:
    """Return the UTF-8 text content of a file inside the project sandbox."""
    try:
        p = _safe_path(project_id, path)
    except PathSandboxError as e:
        return _err(str(e))

    if not p.exists():
        return _err(f"File not found: {path}")
    if not p.is_file():
        return _err(f"Not a file: {path}")

    try:
        data = p.read_bytes()
    except OSError as e:
        return _err(f"Could not read file: {e}")

    truncated = len(data) > max_bytes
    if truncated:
        data = data[:max_bytes]

    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return _err(f"File is not valid UTF-8 text (binary?): {path}")

    return _ok(path=path, content=text, truncated=truncated, size_bytes=p.stat().st_size)


# ── write_file ────────────────────────────────────────────────────────────

def write_file(project_id: str, path: str, content: str) -> dict:
    """Create or overwrite a file inside the project sandbox. Creates
    parent directories as needed."""
    try:
        p = _safe_path(project_id, path)
    except PathSandboxError as e:
        return _err(str(e))

    if p.exists() and p.is_dir():
        return _err(f"Path is a directory, not a file: {path}")

    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        existed = p.exists()
        # Use newline="" so Python never translates \n → \r\n on Windows;
        # callers always get exactly the bytes they passed as content.
        with open(p, "w", newline="", encoding="utf-8") as fh:
            fh.write(content)
    except OSError as e:
        return _err(f"Could not write file: {e}")

    return _ok(path=path, bytes_written=len(content.encode("utf-8")), created=not existed)


# ── Hub-level specs/ sandbox (for planning agents, not specialists) ────────
#
# specs/ is a hub-level concern (it's the system's shared memory — see
# hub/memory/spec_loader.py), not per-project source code, so it
# deliberately lives outside workspace/projects/<project_id>/. Planning
# agents (Orchestrator, Feature Lead — see hub/agents/) get their own,
# separate sandbox restricted to specs/ so they can persist plans and
# specs without ever being able to touch project source, config, or
# anything else at the hub root. Specialists never use these — they stay
# inside the project sandbox via read_file/write_file above.

SPECS_ROOT = (ROOT / "specs").resolve()
SPECS_ROOT.mkdir(parents=True, exist_ok=True)


def _safe_specs_path(rel_path: str) -> Path:
    """Resolve rel_path (e.g. 'specs/features/F01-auth.md') against the
    hub root, but only allow it through if it lands inside specs/."""
    if rel_path in (None, ""):
        raise PathSandboxError("Spec path must not be empty")

    candidate = Path(rel_path)
    if _looks_absolute(rel_path):
        raise PathSandboxError(f"Absolute paths are not allowed: {rel_path!r}")

    resolved = (ROOT / candidate).resolve()
    try:
        resolved.relative_to(SPECS_ROOT)
    except ValueError:
        raise PathSandboxError(f"Path '{rel_path}' is outside the specs/ sandbox")

    return resolved


def read_spec_file(path: str) -> dict:
    """Read a file under specs/ (e.g. 'specs/features/F01-auth.md').
    Same return contract as read_file, sandboxed to specs/ instead of a
    project workspace."""
    try:
        p = _safe_specs_path(path)
    except PathSandboxError as e:
        return _err(str(e))

    if not p.exists():
        return _err(f"Spec file not found: {path}")
    if not p.is_file():
        return _err(f"Not a file: {path}")

    try:
        content = p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return _err(f"Could not read spec file: {e}")

    return _ok(path=path, content=content)


def write_spec_file(path: str, content: str) -> dict:
    """Create or overwrite a file under specs/ (e.g.
    'specs/features/F01-auth.md', 'specs/tasks/F01/T01-models.md').
    Creates parent directories as needed. Used by planning agents only —
    specialists use write_file, which is sandboxed to the project
    workspace instead."""
    try:
        p = _safe_specs_path(path)
    except PathSandboxError as e:
        return _err(str(e))

    if p.exists() and p.is_dir():
        return _err(f"Path is a directory, not a file: {path}")

    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        existed = p.exists()
        p.write_text(content, encoding="utf-8")
    except OSError as e:
        return _err(f"Could not write spec file: {e}")

    return _ok(path=path, bytes_written=len(content.encode("utf-8")), created=not existed)


# ── apply_patch ───────────────────────────────────────────────────────────

_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def _apply_unified_diff(original: str, diff_text: str) -> str:
    """Apply a unified-diff hunk body to `original`, returning the patched
    text. Supports standard '+', '-', ' ' (context) lines and multiple
    hunks. Does not require a system `patch` binary."""
    orig_lines = original.splitlines(keepends=True)
    diff_lines = diff_text.splitlines()

    result: list = []
    orig_idx = 0
    i = 0
    n = len(diff_lines)

    # Skip optional file header lines (--- a/x, +++ b/x)
    while i < n and (diff_lines[i].startswith("---") or diff_lines[i].startswith("+++")):
        i += 1

    saw_hunk = False
    while i < n:
        m = _HUNK_RE.match(diff_lines[i])
        if not m:
            i += 1
            continue
        saw_hunk = True
        old_start = int(m.group(1))
        target_idx = max(old_start - 1, 0)

        if target_idx > len(orig_lines):
            raise ValueError(f"Hunk references line {old_start}, but file only has {len(orig_lines)} lines")
        if target_idx > orig_idx:
            result.extend(orig_lines[orig_idx:target_idx])
            orig_idx = target_idx

        i += 1
        while i < n and not diff_lines[i].startswith("@@"):
            hl = diff_lines[i]
            if hl.startswith("-") and not hl.startswith("---"):
                orig_idx += 1
            elif hl.startswith("+") and not hl.startswith("+++"):
                newline = "\n" if (orig_idx >= len(orig_lines) or orig_lines[orig_idx].endswith("\n")) else ""
                result.append(hl[1:] + newline)
            elif hl.startswith("\\"):
                pass  # "\ No newline at end of file"
            else:
                # context line (leading space) or blank line treated as context
                content = hl[1:] if hl.startswith(" ") else hl
                if orig_idx < len(orig_lines):
                    result.append(orig_lines[orig_idx])
                else:
                    result.append(content + "\n")
                orig_idx += 1
            i += 1

    if not saw_hunk:
        raise ValueError("No valid '@@ ... @@' hunk header found in diff")

    result.extend(orig_lines[orig_idx:])
    return "".join(result)


def apply_patch(project_id: str, path: str, diff: str) -> dict:
    """Apply a unified-diff string to an existing file inside the project
    sandbox. Prefer this over write_file for small, targeted edits."""
    try:
        p = _safe_path(project_id, path)
    except PathSandboxError as e:
        return _err(str(e))

    if not p.exists():
        return _err(f"File not found (cannot patch a missing file): {path}")

    try:
        # newline="" on both read and write: without it, Python's default
        # text-mode translation converts \n -> \r\n on write (and reads
        # would silently normalize \r\n -> \n), so a patched file's
        # content stops matching what was passed in. This mirrors the
        # same newline="" used in write_file() above.
        #
        # NOTE: Path.read_text()/write_text() only gained a newline=
        # parameter in Python 3.13, so on 3.12 and earlier we have to use
        # open() directly instead — passing newline= to read_text/write_text
        # on those versions raises TypeError.
        with open(p, "r", encoding="utf-8", newline="") as fh:
            original = fh.read()
    except (OSError, UnicodeDecodeError) as e:
        return _err(f"Could not read file to patch: {e}")

    try:
        patched = _apply_unified_diff(original, diff)
    except ValueError as e:
        return _err(f"Failed to apply patch: {e}")

    try:
        with open(p, "w", encoding="utf-8", newline="") as fh:
            fh.write(patched)
    except OSError as e:
        return _err(f"Could not write patched file: {e}")

    return _ok(path=path, bytes_written=len(patched.encode("utf-8")))


# ── list_dir ──────────────────────────────────────────────────────────────

def list_dir(project_id: str, path: str = ".", max_depth: int = 4, max_entries: int = MAX_DIR_ENTRIES) -> dict:
    """Return a tree listing of a directory inside the project sandbox."""
    try:
        p = _safe_path(project_id, path)
    except PathSandboxError as e:
        return _err(str(e))

    if not p.exists():
        return _err(f"Path not found: {path}")
    if not p.is_dir():
        return _err(f"Not a directory: {path}")

    entries = []
    truncated = False

    def walk(d: Path, depth: int):
        nonlocal truncated
        if depth > max_depth:
            return
        try:
            children = sorted(d.iterdir(), key=lambda c: (c.is_file(), c.name.lower()))
        except OSError:
            return
        for child in children:
            if child.name in _SKIP_DIR_NAMES:
                continue
            if len(entries) >= max_entries:
                truncated = True
                return
            rel = child.relative_to(p).as_posix()
            if child.is_dir():
                entries.append({"path": rel, "type": "dir"})
                walk(child, depth + 1)
            else:
                try:
                    size = child.stat().st_size
                except OSError:
                    size = None
                entries.append({"path": rel, "type": "file", "size_bytes": size})

    walk(p, 1)
    return _ok(path=path, entries=entries, truncated=truncated, count=len(entries))


# ── search_code ───────────────────────────────────────────────────────────

def _search_with_ripgrep(proj_root: Path, query: str, search_path: Path, max_results: int) -> list:
    cmd = ["rg", "--line-number", "--no-heading", "--color=never", "-m", "200", query, str(search_path)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    results = []
    if proc.returncode not in (0, 1):  # 1 == no matches, still success
        raise RuntimeError(proc.stderr.strip() or "ripgrep failed")
    for line in proc.stdout.splitlines():
        parts = line.split(":", 2)
        if len(parts) < 3:
            continue
        file_part, line_no, text = parts
        try:
            file_rel = Path(file_part).resolve().relative_to(proj_root).as_posix()
        except ValueError:
            continue
        results.append({"path": file_rel, "line": int(line_no), "text": text.strip()[:300]})
        if len(results) >= max_results:
            break
    return results


def _search_with_python(proj_root: Path, query: str, search_path: Path, max_results: int) -> list:
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    results = []
    for file_path in search_path.rglob("*"):
        if len(results) >= max_results:
            break
        if not file_path.is_file():
            continue
        if any(part in _SKIP_DIR_NAMES for part in file_path.relative_to(proj_root).parts):
            continue
        try:
            text = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if pattern.search(line):
                results.append({"path": file_path.relative_to(proj_root).as_posix(), "line": lineno, "text": line.strip()[:300]})
                if len(results) >= max_results:
                    break
    return results


def search_code(project_id: str, query: str, path: str = ".", max_results: int = MAX_SEARCH_RESULTS) -> dict:
    """Search file contents for `query` inside the project sandbox.
    Uses ripgrep if available, otherwise a pure-Python fallback."""
    if not query:
        return _err("query must be a non-empty string")

    try:
        p = _safe_path(project_id, path)
    except PathSandboxError as e:
        return _err(str(e))

    proj_root = _project_root(project_id)
    engine = "ripgrep" if shutil.which("rg") else "python-fallback"

    try:
        if engine == "ripgrep":
            results = _search_with_ripgrep(proj_root, query, p, max_results)
        else:
            results = _search_with_python(proj_root, query, p, max_results)
    except Exception as e:
        return _err(f"Search failed: {e}")

    return _ok(query=query, engine=engine, matches=results, count=len(results))


# ── run_terminal ──────────────────────────────────────────────────────────

# Base commands allowed at all (deny-by-default for anything not listed here)
_ALLOWED_BASE_COMMANDS = {
    "python", "python3", "pytest", "pip", "pip3",
    "node", "npm", "npx", "yarn",
    "git", "ls", "cat", "echo", "pwd", "mkdir", "touch", "cp", "mv",
    "find", "grep", "rg", "diff", "wc", "head", "tail", "sort", "uniq",
    "go", "cargo", "javac", "java", "mvn", "make",
    "rm", "curl", "wget", "chmod",  # allowed, but gated below
}

# Always blocked, even with approval=True — too easy to escape the sandbox
_ALWAYS_BLOCKED_BASE_COMMANDS = {
    "sudo", "su", "ssh", "scp", "rsync", "dd", "mkfs",
    "shutdown", "reboot", "kill", "killall", "chown", "doas",
}

# Base commands that need human approval before running
_NEEDS_APPROVAL_BASE_COMMANDS = {"rm", "curl", "wget", "chmod"}

# Specific phrases that need human approval regardless of base command
_NEEDS_APPROVAL_PHRASES = (
    "pip install", "pip3 install", "npm install", "npm i ", "yarn add",
    "git push", "git reset --hard", "git clean -f", "git checkout -- .",
)


def _split_segments(cmd: str) -> list:
    """Naively split a shell command on chaining operators so each
    segment's leading command can be checked against the allowlist.
    Does not attempt to parse quoting around these operators."""
    return [seg.strip() for seg in re.split(r"&&|\|\||\||;", cmd) if seg.strip()]


def _classify_command(cmd: str) -> dict:
    """Inspect a full shell command string and decide whether it can run,
    needs approval, or is blocked outright."""
    segments = _split_segments(cmd)
    if not segments:
        return {"verdict": "blocked", "reason": "Empty command"}

    needs_approval = False
    for seg in segments:
        try:
            tokens = shlex.split(seg)
        except ValueError as e:
            return {"verdict": "blocked", "reason": f"Could not parse command segment '{seg}': {e}"}
        if not tokens:
            continue
        base = tokens[0]

        if base in _ALWAYS_BLOCKED_BASE_COMMANDS:
            return {"verdict": "blocked", "reason": f"Command '{base}' is never allowed"}
        if base not in _ALLOWED_BASE_COMMANDS:
            return {"verdict": "blocked", "reason": f"Command '{base}' is not on the allowlist"}
        if base in _NEEDS_APPROVAL_BASE_COMMANDS:
            needs_approval = True
        if any(phrase in seg for phrase in _NEEDS_APPROVAL_PHRASES):
            needs_approval = True

    return {"verdict": "needs_approval" if needs_approval else "allowed", "reason": None}


@functools.lru_cache(maxsize=1)
def _docker_available() -> bool:
    """True only if `docker` is on PATH AND the daemon actually answers.

    shutil.which("docker") alone isn't enough: on many dev machines
    (especially Windows with Docker Desktop) the CLI is installed but the
    daemon isn't running. In that case `docker run ...` fails immediately,
    but this code doesn't check proc.returncode before returning ok=True,
    so callers silently got empty stdout / failing pytest runs instead of
    a clear error. Probing `docker info` up front lets us fall back to
    the local subprocess instead.
    """
    if shutil.which("docker") is None:
        return False
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def run_terminal(
    project_id: str,
    cmd: str,
    cwd: str = ".",
    approved: bool = False,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict:
    """Run a shell command sandboxed to the project workspace. Runs inside
    Docker when available, otherwise falls back to a local subprocess
    confined to `cwd`. Destructive commands (rm, curl, wget, chmod, pip/npm
    install, git push, ...) require approved=True; unknown commands and a
    short list of always-dangerous commands (sudo, ssh, dd, ...) are
    blocked outright."""
    try:
        safe_cwd = _safe_path(project_id, cwd)
    except PathSandboxError as e:
        return _err(str(e))

    if not safe_cwd.exists():
        return _err(f"cwd does not exist: {cwd}")

    verdict = _classify_command(cmd)
    if verdict["verdict"] == "blocked":
        return _err(f"Command blocked: {verdict['reason']}", cmd=cmd)
    if verdict["verdict"] == "needs_approval" and not approved:
        return _err(
            "Command requires human approval (set approved=True to run)",
            cmd=cmd,
            requires_approval=True,
        )

    proj_root = _project_root(project_id)
    rel_cwd = safe_cwd.relative_to(proj_root)
    started = time.time()

    try:
        if _docker_available():
            container_cwd = f"/workspace/{rel_cwd}" if str(rel_cwd) != "." else "/workspace"
            docker_cmd = [
                "docker", "run", "--rm",
                "--network", "none",
                "-v", f"{proj_root}:/workspace",
                "-w", container_cwd,
                DEFAULT_DOCKER_IMAGE,
                "sh", "-c", cmd,
            ]
            proc = subprocess.run(docker_cmd, capture_output=True, text=True, timeout=timeout)
            sandbox_mode = "docker"
        else:
            proc = subprocess.run(
                cmd, shell=True, cwd=str(safe_cwd),
                capture_output=True, text=True, timeout=timeout,
            )
            sandbox_mode = "local-fallback"
    except subprocess.TimeoutExpired:
        return _err(f"Command timed out after {timeout}s", cmd=cmd)
    except OSError as e:
        return _err(f"Failed to execute command: {e}", cmd=cmd)

    duration = round(time.time() - started, 3)
    return _ok(
        cmd=cmd,
        sandbox_mode=sandbox_mode,
        returncode=proc.returncode,
        stdout=proc.stdout[-20_000:],
        stderr=proc.stderr[-20_000:],
        duration_seconds=duration,
    )


# ── run_tests ─────────────────────────────────────────────────────────────

def run_tests(project_id: str, suite: Optional[str] = None, cwd: str = ".", timeout: int = DEFAULT_TIMEOUT_SECONDS) -> dict:
    """Run the project's test suite. `suite` may be a path/module passed
    straight to pytest (e.g. 'tests/test_user_model.py'); omit it to run
    the whole suite."""
    cmd = "pytest -q" if not suite else f"pytest -q {shlex.quote(suite)}"
    result = run_terminal(project_id, cmd, cwd=cwd, approved=True, timeout=timeout)
    if not result["ok"]:
        return result
    result["passed"] = result["returncode"] == 0
    return result


# ── git_status / git_commit ──────────────────────────────────────────────

def _ensure_git_repo(proj_root: Path) -> bool:
    """Return True if proj_root is (or now is) a git repo; init if missing."""
    if (proj_root / ".git").exists():
        return True
    proc = subprocess.run(["git", "init"], cwd=str(proj_root), capture_output=True, text=True)
    return proc.returncode == 0


def git_status(project_id: str) -> dict:
    """Return `git status --porcelain` for the project, initializing a
    git repo if one doesn't exist yet."""
    proj_root = _project_root(project_id)
    initialized_now = not (proj_root / ".git").exists()

    if not _ensure_git_repo(proj_root):
        return _err("Could not initialize git repository")

    proc = subprocess.run(
        ["git", "status", "--porcelain=v1", "--branch"],
        cwd=str(proj_root), capture_output=True, text=True,
    )
    if proc.returncode != 0:
        return _err(f"git status failed: {proc.stderr.strip()}")

    lines = proc.stdout.splitlines()
    branch_line = lines[0] if lines and lines[0].startswith("##") else None
    changes = lines[1:] if branch_line else lines

    return _ok(
        branch=branch_line.lstrip("# ").strip() if branch_line else None,
        changes=changes,
        clean=len(changes) == 0,
        initialized_now=initialized_now,
    )


def git_commit(project_id: str, message: str) -> dict:
    """Stage all changes and commit them inside the project sandbox.
    Initializes the repo if needed; reports nothing_to_commit=True
    instead of erroring when the working tree is already clean."""
    if not message or not message.strip():
        return _err("Commit message must not be empty")

    proj_root = _project_root(project_id)
    if not _ensure_git_repo(proj_root):
        return _err("Could not initialize git repository")

    add_proc = subprocess.run(["git", "add", "-A"], cwd=str(proj_root), capture_output=True, text=True)
    if add_proc.returncode != 0:
        return _err(f"git add failed: {add_proc.stderr.strip()}")

    # Configure a default identity if none exists yet (fresh sandbox repos)
    id_check = subprocess.run(["git", "config", "user.email"], cwd=str(proj_root), capture_output=True, text=True)
    if id_check.returncode != 0 or not id_check.stdout.strip():
        subprocess.run(["git", "config", "user.email", "agent@my-agent-hub.local"], cwd=str(proj_root), capture_output=True, text=True)
        subprocess.run(["git", "config", "user.name", "my-agent-hub"], cwd=str(proj_root), capture_output=True, text=True)

    commit_proc = subprocess.run(
        ["git", "commit", "-m", message],
        cwd=str(proj_root), capture_output=True, text=True,
    )

    if commit_proc.returncode != 0:
        if "nothing to commit" in (commit_proc.stdout + commit_proc.stderr).lower():
            return _ok(commit_sha=None, nothing_to_commit=True)
        return _err(f"git commit failed: {commit_proc.stderr.strip() or commit_proc.stdout.strip()}")

    sha_proc = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=str(proj_root), capture_output=True, text=True)
    commit_sha = sha_proc.stdout.strip() if sha_proc.returncode == 0 else None

    return _ok(commit_sha=commit_sha, message=message, nothing_to_commit=False)


# ── Per-project convenience wrapper (for ADK FunctionTool registration) ───

class ProjectTools:
    """Binds a single project_id and exposes the tool functions with the
    exact signatures specialist agents expect (no project_id param), so
    they can be wrapped directly as ADK FunctionTools, e.g.:

        tools = ProjectTools(project_id)
        coder_agent = Agent(..., tools=[
            FunctionTool(tools.read_file),
            FunctionTool(tools.write_file),
        ])
    """

    def __init__(self, project_id: str):
        self.project_id = project_id

    def read_file(self, path: str) -> dict:
        """Return the UTF-8 text content of a file."""
        return read_file(self.project_id, path)

    def write_file(self, path: str, content: str) -> dict:
        """Create or overwrite a file with the given content."""
        return write_file(self.project_id, path, content)

    def apply_patch(self, path: str, diff: str) -> dict:
        """Apply a unified-diff string to an existing file."""
        return apply_patch(self.project_id, path, diff)

    def list_dir(self, path: str = ".") -> dict:
        """Return a tree listing of a directory."""
        return list_dir(self.project_id, path)

    def search_code(self, query: str, path: str = ".") -> dict:
        """Search file contents for a query string."""
        return search_code(self.project_id, query, path)

    def run_terminal(self, cmd: str, cwd: str = ".", approved: bool = False) -> dict:
        """Run a shell command. Destructive commands need approved=True."""
        return run_terminal(self.project_id, cmd, cwd=cwd, approved=approved)

    def git_status(self) -> dict:
        """Return git status for the project."""
        return git_status(self.project_id)

    def git_commit(self, message: str) -> dict:
        """Stage all changes and commit them."""
        return git_commit(self.project_id, message)

    def run_tests(self, suite: Optional[str] = None, cwd: str = ".") -> dict:
        """Run the project's test suite (optionally a specific suite/path)."""
        return run_tests(self.project_id, suite, cwd=cwd)
