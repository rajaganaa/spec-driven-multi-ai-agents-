"""
hub/memory/spec_loader.py — Part C: Spec System + Memory
==========================================================

Pure-Python spec/memory layer. No LLM calls, no ADK agent code — that
lives in Part D/E. This module is the thing agents read from and the
thing the runner writes status into.

WHAT LIVES WHERE
-----------------
    specs/features/F*.md         feature specs   (load_spec)
    specs/tasks/<feature>/T*.md  task specs       (load_spec, build_agent_context)
    specs/tasks/T*.md            task specs, flat (back-compat with the
                                  current scaffold — see note below)
    status/board.json            single global board (update_board_status)
    project.meta.json            source of the active project_id used to
                                  resolve project-sandboxed context files

NOTE ON TASK SPEC LAYOUT: the blueprint and config/agents.yaml describe
task specs as living under specs/tasks/<feature>/T*.md, but the current
scaffold's example (specs/tasks/T01-example.md) is flat. find_task_spec()
/ build_agent_context() search both layouts, so either convention works
going forward — Part D/E can write nested-per-feature without anything
here needing to change.

SPEC FORMAT
-----------
load_spec() parses the exact markdown structure used by
specs/features/F01-example.md and specs/tasks/T01-example.md: a single
`# ID: Title` heading followed by `## Section` blocks. Known sections
are parsed into typed fields (checklists -> list[{"text","done"}],
file/bullet lists -> list[str], scalars -> str); unknown sections are
still captured (as raw text) so new headers don't break parsing.
`.json` spec files are also accepted and returned as parsed JSON.

CONTEXT FILES: SPEC PATHS VS PROJECT PATHS
-------------------------------------------
A task's "Context Files" list mixes two kinds of paths, e.g.:
    - `specs/features/F01-example.md`   <- hub-level, NOT in the sandbox
    - `src/module/file.py`              <- project-level, IS in the sandbox

build_agent_context() tries hub.tools.tools.read_file(project_id, path)
first (covers project-sandboxed source files), and falls back to a
direct read from the hub root for paths that live outside
workspace/projects/<project_id>/ (specs/, config/, etc.).

RETURN CONTRACT
---------------
Every public function here returns the same shape as the tools layer:

    {"ok": True,  "error": None, ...data...}
    {"ok": False, "error": "<message>", ...partial data...}

TOKEN BUDGET
------------
No tokenizer dependency is in requirements.txt, so token counts are a
rough ~4-chars-per-token estimate (_estimate_tokens). Files are loaded
in the order listed; once the budget is hit, the file in progress is
truncated to fit and every remaining file is skipped (not read at all).
Defaults mirror config/agents.yaml's workspace.max_context_files /
workspace.max_context_tokens.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from hub.tools import tools

# ── Paths ─────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent.parent  # .../my-agent-hub
SPECS_DIR = ROOT / "specs"
FEATURES_DIR = SPECS_DIR / "features"
TASKS_DIR = SPECS_DIR / "tasks"
BOARD_PATH = ROOT / "status" / "board.json"
META_PATH = ROOT / "project.meta.json"

MAX_CONTEXT_FILES = 5
MAX_CONTEXT_TOKENS = 15000


# ── Result helpers (same shape as hub/tools/tools.py) ──────────────────────

def _ok(**kwargs) -> dict:
    return {"ok": True, "error": None, **kwargs}


def _err(message: str, **kwargs) -> dict:
    return {"ok": False, "error": message, **kwargs}


# ── Markdown section parsing ────────────────────────────────────────────────

_HEADER_KEY_MAP = {
    "goal": "goal",
    "acceptance criteria": "acceptance_criteria",
    "files likely touched": "files_likely_touched",
    "dependencies": "dependencies",
    "assigned lead": "assigned_lead",
    "status": "status",
    "feature": "feature",
    "role": "role",
    "context files": "context_files",
    "instructions": "instructions",
    "definition of done": "definition_of_done",
}

LIST_SECTIONS = {"files_likely_touched", "dependencies", "context_files", "definition_of_done"}
CHECKLIST_SECTIONS = {"acceptance_criteria"}
SCALAR_SECTIONS = {"goal", "assigned_lead", "status", "feature", "role"}
RAW_SECTIONS = {"instructions"}


def _normalize_header(header: str) -> str:
    """'Context Files (max 5)' -> 'context files'."""
    h = re.sub(r"\(.*?\)", "", header).strip().lower()
    return re.sub(r"\s+", " ", h)


def _header_key(header: str) -> str:
    norm = _normalize_header(header)
    if norm in _HEADER_KEY_MAP:
        return _HEADER_KEY_MAP[norm]
    # Unknown header: still produce a stable key so it's captured, not dropped.
    return re.sub(r"\W+", "_", norm).strip("_") or "section"


def _parse_markdown_sections(text: str) -> Tuple[str, Dict[str, str], List[str]]:
    """Split markdown on `## Header` lines. Returns (preamble,
    {header_key: raw_body}, [header_key, ...] in original order)."""
    parts = re.split(r"(?m)^##[ \t]+(.+?)[ \t]*$", text)
    preamble = parts[0]
    sections: Dict[str, str] = {}
    order: List[str] = []
    for i in range(1, len(parts), 2):
        header = parts[i]
        body = parts[i + 1] if i + 1 < len(parts) else ""
        key = _header_key(header)
        sections[key] = body.strip("\n")
        order.append(key)
    return preamble, sections, order


def _parse_title(preamble: str) -> Tuple[Optional[str], Optional[str]]:
    """'# F01: Example Feature' -> ('F01', 'Example Feature')."""
    m = re.search(r"(?m)^#[ \t]+(.+?)[ \t]*$", preamble)
    if not m:
        return None, None
    title_line = m.group(1).strip()
    m2 = re.match(r"^([A-Za-z]+\d+[A-Za-z0-9]*)\s*:\s*(.+)$", title_line)
    if m2:
        return m2.group(1), m2.group(2).strip()
    return None, title_line


def _parse_bullets(body: str) -> List[str]:
    """'- `src/x.py`' -> 'src/x.py'; '- F00: scaffold' -> 'F00: scaffold'."""
    items: List[str] = []
    for line in body.splitlines():
        line = line.strip()
        if not line.startswith("-"):
            continue
        content = line[1:].strip()
        m = re.fullmatch(r"`([^`]+)`", content)
        if m:
            content = m.group(1)
        if content:
            items.append(content)
    return items


_CHECKLIST_RE = re.compile(r"^-\s*\[([ xX])\]\s*(.+)$")


def _parse_checklist(body: str) -> List[dict]:
    items: List[dict] = []
    for line in body.splitlines():
        m = _CHECKLIST_RE.match(line.strip())
        if m:
            items.append({"text": m.group(2).strip(), "done": m.group(1).strip().lower() == "x"})
    return items


def _resolve_spec_path(spec_path: str) -> Path:
    p = Path(spec_path)
    return p if p.is_absolute() else (ROOT / p)


# ── load_spec ────────────────────────────────────────────────────────────

def load_spec(spec_path: str) -> dict:
    """Read a feature or task spec file and parse it into a structured
    dict. Accepts .md (the real format used in this hub) and .json.
    No LLM calls."""
    path = _resolve_spec_path(spec_path)

    if not path.exists():
        return _err(f"Spec file not found: {spec_path}")
    if not path.is_file():
        return _err(f"Not a file: {spec_path}")

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        return _err(f"Could not read spec file: {e}")
    except UnicodeDecodeError:
        return _err(f"Spec file is not valid UTF-8 text: {spec_path}")

    if path.suffix.lower() == ".json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            return _err(f"Invalid JSON spec: {e}")
        extra = data if isinstance(data, dict) else {"data": data}
        return _ok(path=str(path), format="json", **extra)

    preamble, sections, order = _parse_markdown_sections(text)
    spec_id, title = _parse_title(preamble)

    parsed: Dict[str, object] = {}
    for key in order:
        if key in LIST_SECTIONS:
            parsed[key] = _parse_bullets(sections[key])
        elif key in CHECKLIST_SECTIONS:
            parsed[key] = _parse_checklist(sections[key])
        elif key in SCALAR_SECTIONS:
            value = sections[key].strip()
            if key == "role":
                value = value.split("#", 1)[0].strip()
            parsed[key] = value
        elif key in RAW_SECTIONS:
            parsed[key] = sections[key].strip()
        elif key not in parsed:
            # Unknown header: capture raw text rather than discard it.
            parsed[key] = sections[key].strip()

    if spec_id and spec_id.upper().startswith("F"):
        spec_type = "feature"
    elif spec_id and spec_id.upper().startswith("T"):
        spec_type = "task"
    elif "feature" in sections:
        spec_type = "task"
    elif "assigned_lead" in sections:
        spec_type = "feature"
    else:
        spec_type = "unknown"

    return _ok(
        path=str(path),
        format="markdown",
        type=spec_type,
        id=spec_id,
        title=title,
        sections_present=order,
        raw_sections=sections,
        **parsed,
    )


# ── Task spec lookup ──────────────────────────────────────────────────────

def find_task_spec_path(task_id: str) -> Optional[Path]:
    """Locate a task spec file by id, searching both the documented
    nested layout (specs/tasks/<feature>/T*.md) and the flat layout
    used by the current scaffold example (specs/tasks/T*.md)."""
    if not TASKS_DIR.exists() or not task_id:
        return None

    candidates: List[Path] = []
    for p in sorted(TASKS_DIR.glob("*/*.md")):
        if p.stem.lower().startswith(task_id.lower()):
            candidates.append(p)
    for p in sorted(TASKS_DIR.glob("*.md")):
        if p.stem.lower().startswith(task_id.lower()):
            candidates.append(p)

    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    # Disambiguate T1 vs T10-style prefix collisions where possible.
    exact = [p for p in candidates if re.match(rf"^{re.escape(task_id)}(?:[-_].*)?$", p.stem, re.IGNORECASE)]
    return exact[0] if len(exact) == 1 else candidates[0]


def _get_active_project_id() -> Optional[str]:
    if not META_PATH.exists():
        return None
    try:
        meta = json.loads(META_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    pid = meta.get("project_id") if isinstance(meta, dict) else None
    return pid if isinstance(pid, str) and pid else None


def get_active_project_id() -> Optional[str]:
    """Public wrapper around the active project's id, read from
    project.meta.json. Used by hub/agents/ (Orchestrator, Feature Lead)
    to resolve which project a planning run applies to."""
    return _get_active_project_id()


def load_project_meta() -> dict:
    """Read project.meta.json (goal, stack, constraints, ...). Same
    {"ok"/"error"} contract as the rest of this module."""
    if not META_PATH.exists():
        return _err(f"project.meta.json not found at {META_PATH}")
    try:
        meta = json.loads(META_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return _err(f"Could not read project.meta.json: {e}")
    if not isinstance(meta, dict):
        return _err("project.meta.json does not contain a JSON object")
    return _ok(**meta)


def _estimate_tokens(text: str) -> int:
    """Rough ~4-chars-per-token estimate. No tokenizer dependency."""
    return max(1, len(text) // 4) if text else 0


def _read_context_file(project_id: Optional[str], rel_path: str) -> dict:
    """Load one context-file's content: try the project sandbox first
    (covers project source files), then fall back to a direct read from
    the hub root (covers specs/, config/, etc., which live outside
    workspace/projects/<project_id>/ by design)."""
    sandbox_result = None
    if project_id:
        sandbox_result = tools.read_file(project_id, rel_path)
        if sandbox_result.get("ok"):
            return sandbox_result

    direct = _resolve_spec_path(rel_path)
    if direct.exists() and direct.is_file():
        try:
            content = direct.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            return _err(f"Could not read file: {e}", path=rel_path)
        return _ok(path=rel_path, content=content, truncated=False, size_bytes=direct.stat().st_size)

    if sandbox_result is not None:
        return sandbox_result  # the sandboxed error is the more informative one
    return _err(f"File not found: {rel_path}", path=rel_path)


# ── build_agent_context ────────────────────────────────────────────────────

def build_agent_context(
    task_id: str,
    max_files: int = MAX_CONTEXT_FILES,
    max_tokens: int = MAX_CONTEXT_TOKENS,
) -> dict:
    """Given a task id, load its task spec plus (up to max_files) listed
    context files, capped at ~max_tokens total. Returns a dict that is
    the specialist agent's entire prompt context — nothing else, no
    chat history. No LLM calls."""
    spec_path = find_task_spec_path(task_id)
    if spec_path is None:
        return _err(f"No task spec found for task_id: {task_id}")

    task_spec = load_spec(str(spec_path))
    if not task_spec.get("ok"):
        return task_spec
    if task_spec.get("type") not in ("task", "unknown"):
        return _err(
            f"Spec at {spec_path} is not a task spec (type={task_spec.get('type')})",
            path=str(spec_path),
        )

    project_id = _get_active_project_id()
    raw_files = task_spec.get("context_files") or []
    overflow = len(raw_files) > max_files
    files_to_load = raw_files[:max_files]

    context_files: List[dict] = []
    total_tokens = 0
    budget_hit = False

    for rel_path in files_to_load:
        if budget_hit:
            context_files.append({
                "path": rel_path, "included": False, "truncated": False,
                "tokens_estimate": 0, "error": "Skipped: context token budget already exhausted",
            })
            continue

        loaded = _read_context_file(project_id, rel_path)
        if not loaded.get("ok"):
            context_files.append({
                "path": rel_path, "included": False, "truncated": False,
                "tokens_estimate": 0, "error": loaded.get("error", "Unknown error"),
            })
            continue

        content = loaded.get("content", "")
        file_tokens = _estimate_tokens(content)
        remaining = max_tokens - total_tokens

        if file_tokens <= remaining:
            context_files.append({
                "path": rel_path, "included": True,
                "truncated": bool(loaded.get("truncated", False)),
                "tokens_estimate": file_tokens, "content": content, "error": None,
            })
            total_tokens += file_tokens
        elif remaining > 0:
            marker = "\n...[truncated: context token budget reached]"
            marker_tokens = _estimate_tokens(marker)
            keep_chars = max(0, (remaining - marker_tokens)) * 4
            truncated_content = content[:keep_chars] + marker
            truncated_tokens = _estimate_tokens(truncated_content)
            context_files.append({
                "path": rel_path, "included": True, "truncated": True,
                "tokens_estimate": truncated_tokens, "content": truncated_content, "error": None,
            })
            total_tokens += truncated_tokens
            budget_hit = True
        else:
            context_files.append({
                "path": rel_path, "included": False, "truncated": False,
                "tokens_estimate": 0, "error": "Skipped: context token budget exhausted",
            })
            budget_hit = True

    prompt_parts = [f"# Task {task_spec.get('id') or task_id}: {task_spec.get('title') or ''}".rstrip(": ")]
    if task_spec.get("goal"):
        prompt_parts.append(f"## Goal\n{task_spec['goal']}")
    if task_spec.get("role"):
        prompt_parts.append(f"## Role\n{task_spec['role']}")
    if task_spec.get("instructions"):
        prompt_parts.append(f"## Instructions\n{task_spec['instructions']}")
    if task_spec.get("acceptance_criteria"):
        crit = "\n".join(f"- [{'x' if c['done'] else ' '}] {c['text']}" for c in task_spec["acceptance_criteria"])
        prompt_parts.append(f"## Acceptance Criteria\n{crit}")
    if task_spec.get("definition_of_done"):
        dod = "\n".join(f"- {d}" for d in task_spec["definition_of_done"])
        prompt_parts.append(f"## Definition of Done\n{dod}")
    for cf in context_files:
        if cf.get("included"):
            prompt_parts.append(f"## Context File: {cf['path']}\n```\n{cf['content']}\n```")

    return _ok(
        task_id=task_spec.get("id") or task_id,
        feature=task_spec.get("feature"),
        spec_path=str(spec_path),
        task_spec=task_spec,
        project_id=project_id,
        context_files=context_files,
        total_tokens_estimate=total_tokens,
        budget_tokens=max_tokens,
        max_files=max_files,
        context_files_overflow=overflow,
        prompt="\n\n".join(prompt_parts),
    )


# ── update_board_status ─────────────────────────────────────────────────────

def _load_board() -> dict:
    if not BOARD_PATH.exists():
        return {"project_id": _get_active_project_id(), "updated_at": "", "tasks": []}
    try:
        data = json.loads(BOARD_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise ValueError(f"status/board.json is corrupted or unreadable: {e}")
    if not isinstance(data, dict):
        raise ValueError("status/board.json does not contain a JSON object")
    data.setdefault("project_id", _get_active_project_id())
    data.setdefault("updated_at", "")
    data.setdefault("tasks", [])
    if not isinstance(data["tasks"], list):
        raise ValueError("status/board.json 'tasks' field is not a list")
    return data


def _save_board(board: dict) -> None:
    BOARD_PATH.parent.mkdir(parents=True, exist_ok=True)
    BOARD_PATH.write_text(json.dumps(board, indent=2) + "\n", encoding="utf-8")


def list_tasks(status: Optional[str] = None) -> List[dict]:
    """Tasks from status/board.json, optionally filtered by status (e.g.
    'pending'). Returns [] if the board doesn't exist yet or is
    corrupted, rather than raising — callers like hub/runner/task_runner.py
    treat "no work found" and "board unreadable" the same way."""
    if not BOARD_PATH.exists():
        return []
    try:
        board = _load_board()
    except ValueError:
        return []
    tasks = board.get("tasks", [])
    if status is None:
        return list(tasks)
    return [t for t in tasks if isinstance(t, dict) and t.get("status") == status]


def update_board_status(
    task_id: str,
    status: str,
    commit: Optional[str] = None,
    agent: Optional[str] = None,
) -> dict:
    """Update (or create) the matching task entry in status/board.json.
    Only overwrites agent/commit when explicitly provided, so a status
    update never silently wipes a previously recorded commit or agent.
    Returns {"ok": bool, "error": ...} in the same shape as the tools
    layer."""
    if not task_id or not isinstance(task_id, str):
        return _err(f"Invalid task_id: {task_id!r}")
    if not status or not isinstance(status, str):
        return _err(f"Invalid status: {status!r}")

    try:
        board = _load_board()
    except ValueError as e:
        return _err(str(e))

    tasks = board["tasks"]
    entry = next((t for t in tasks if isinstance(t, dict) and t.get("id") == task_id), None)
    created = entry is None

    if entry is None:
        feature = None
        spec_path = find_task_spec_path(task_id)
        if spec_path is not None:
            spec = load_spec(str(spec_path))
            if spec.get("ok"):
                feature = spec.get("feature")
        entry = {"id": task_id, "feature": feature, "status": status, "agent": agent, "commit": commit}
        tasks.append(entry)
    else:
        entry["status"] = status
        if agent is not None:
            entry["agent"] = agent
        if commit is not None:
            entry["commit"] = commit

    board["updated_at"] = datetime.now(timezone.utc).isoformat()

    try:
        _save_board(board)
    except OSError as e:
        return _err(f"Could not write status/board.json: {e}")

    return _ok(task=dict(entry), board_path=str(BOARD_PATH), created=created)
