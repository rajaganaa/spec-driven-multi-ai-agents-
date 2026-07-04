"""
tests/test_tools.py — Part B unit tests

Focus areas:
  1. Path sandbox: every tool must refuse to touch anything outside
     workspace/projects/<project_id>/
  2. Core happy-path behavior for each tool
  3. run_terminal's allowlist / approval-gating logic
"""

import json
import os
import stat
import shutil
import sys
import time
from pathlib import Path
from typing import Optional

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from hub.tools import tools as T  # noqa: E402


PROJECT = "test-sandbox-project"


def _force_remove_readonly(func, path, exc_info):
    """
    shutil.rmtree error handler for Windows.

    Git marks files under .git/objects/ (and sometimes .git/*) as read-only.
    On POSIX, rmtree can delete read-only files fine because deletion is
    governed by directory permissions, not file permissions. On Windows,
    a read-only file blocks os.unlink() with PermissionError (WinError 5).

    This handler clears the read-only bit and retries the failed operation.
    """
    os.chmod(path, stat.S_IWRITE)
    func(path)


def _rmtree_safe(path: Path, retries: int = 5, delay: float = 0.3) -> None:
    """shutil.rmtree that works even when a .git dir is inside `path`,
    and retries on transient WinError 32 ("The process cannot access
    the file because it is being used by another process").

    That error isn't caused by our own code still holding the file open
    — tools.run_terminal's subprocess.run() call is synchronous and has
    already returned by the time a test finishes. It's Windows Defender
    (or another AV) briefly scanning files git.exe just wrote, a beat
    after the git process itself has exited. The lock clears on its own
    within a few hundred ms, so a short retry/backoff is the standard
    fix — no code elsewhere needs to change, and this never masks a
    real, persistent permission problem (it still raises after
    `retries` attempts)."""
    if not path.exists():
        return
    last_error: Optional[BaseException] = None
    for attempt in range(retries):
        try:
            try:
                # Python 3.12+ uses onexc; older versions use onerror.
                shutil.rmtree(path, onexc=_force_remove_readonly)
            except TypeError:
                shutil.rmtree(path, onerror=_force_remove_readonly)
            return
        except PermissionError as e:
            last_error = e
            time.sleep(delay * (attempt + 1))
    if path.exists() and last_error is not None:
        raise last_error


@pytest.fixture(autouse=True)
def clean_project():
    """Give every test a fresh, empty project directory."""
    proj_dir = T.WORKSPACE_ROOT / PROJECT
    _rmtree_safe(proj_dir)
    yield
    _rmtree_safe(proj_dir)


# ── Path sandbox ──────────────────────────────────────────────────────────

class TestPathSandbox:
    def test_write_then_read_inside_sandbox(self):
        w = T.write_file(PROJECT, "src/app.py", "print('hi')")
        assert w["ok"] is True
        r = T.read_file(PROJECT, "src/app.py")
        assert r["ok"] is True
        assert r["content"] == "print('hi')"

    def test_read_file_blocks_dotdot_traversal(self):
        result = T.read_file(PROJECT, "../../etc/passwd")
        assert result["ok"] is False
        assert "sandbox" in result["error"].lower() or "absolute" in result["error"].lower()

    def test_write_file_blocks_absolute_path(self):
        result = T.write_file(PROJECT, "/etc/passwd", "pwned")
        assert result["ok"] is False
        assert "absolute" in result["error"].lower()

    def test_write_file_blocks_deep_dotdot_escape(self):
        result = T.write_file(PROJECT, "a/b/../../../../../tmp/evil.txt", "pwned")
        assert result["ok"] is False

    def test_list_dir_blocks_traversal(self):
        result = T.list_dir(PROJECT, "../")
        assert result["ok"] is False

    def test_search_code_blocks_traversal(self):
        result = T.search_code(PROJECT, "secret", path="../../")
        assert result["ok"] is False

    def test_run_terminal_blocks_cwd_traversal(self):
        result = T.run_terminal(PROJECT, "ls", cwd="../../")
        assert result["ok"] is False

    def test_invalid_project_id_rejected(self):
        result = T.read_file("../escape", "file.txt")
        assert result["ok"] is False

    def test_symlink_escape_is_blocked(self):
        # Create a symlink inside the sandbox pointing outside it.
        proj_root = T._project_root(PROJECT)
        outside_target = T.ROOT / "tests"  # a real dir outside the sandbox
        link_path = proj_root / "escape_link"
        try:
            link_path.symlink_to(outside_target, target_is_directory=True)
        except OSError as e:
            # Creating symlinks on Windows requires admin rights or
            # Developer Mode enabled (WinError 1314: "A required
            # privilege is not held by the client"). That's a host
            # permission limitation, not something this test can control,
            # so skip rather than fail when we can't even set up the case.
            pytest.skip(f"Cannot create symlinks in this environment: {e}")

        result = T.read_file(PROJECT, "escape_link/test_tools.py")
        assert result["ok"] is False

    def test_writing_two_different_projects_stay_isolated(self):
        T.write_file(PROJECT, "a.txt", "project A")
        T.write_file("test-sandbox-project-2", "a.txt", "project B")
        try:
            r1 = T.read_file(PROJECT, "a.txt")
            r2 = T.read_file("test-sandbox-project-2", "a.txt")
            assert r1["content"] == "project A"
            assert r2["content"] == "project B"
        finally:
            shutil.rmtree(T.WORKSPACE_ROOT / "test-sandbox-project-2", ignore_errors=True)


# ── read_file / write_file ────────────────────────────────────────────────

class TestReadWrite:
    def test_read_missing_file_returns_error(self):
        result = T.read_file(PROJECT, "nope.txt")
        assert result["ok"] is False
        assert "not found" in result["error"].lower()

    def test_write_creates_parent_dirs(self):
        result = T.write_file(PROJECT, "deep/nested/dir/file.txt", "hello")
        assert result["ok"] is True
        assert result["created"] is True
        again = T.write_file(PROJECT, "deep/nested/dir/file.txt", "updated")
        assert again["created"] is False

    def test_write_over_directory_fails(self):
        T.write_file(PROJECT, "somedir/keep.txt", "x")
        result = T.write_file(PROJECT, "somedir", "oops")
        assert result["ok"] is False


# ── apply_patch ───────────────────────────────────────────────────────────

class TestApplyPatch:
    def test_simple_patch_applies(self):
        T.write_file(PROJECT, "greet.py", "line1\nline2\nline3\n")
        diff = (
            "--- a/greet.py\n"
            "+++ b/greet.py\n"
            "@@ -1,3 +1,3 @@\n"
            " line1\n"
            "-line2\n"
            "+line2-changed\n"
            " line3\n"
        )
        result = T.apply_patch(PROJECT, "greet.py", diff)
        assert result["ok"] is True
        content = T.read_file(PROJECT, "greet.py")["content"]
        assert content == "line1\nline2-changed\nline3\n"

    def test_patch_missing_file_errors(self):
        result = T.apply_patch(PROJECT, "nope.py", "@@ -1,1 +1,1 @@\n-x\n+y\n")
        assert result["ok"] is False

    def test_malformed_patch_errors(self):
        T.write_file(PROJECT, "f.py", "x\n")
        result = T.apply_patch(PROJECT, "f.py", "not a real diff")
        assert result["ok"] is False


# ── list_dir / search_code ────────────────────────────────────────────────

class TestListAndSearch:
    def test_list_dir_reports_files_and_dirs(self):
        T.write_file(PROJECT, "src/a.py", "x")
        T.write_file(PROJECT, "src/b.py", "y")
        result = T.list_dir(PROJECT, ".")
        assert result["ok"] is True
        paths = {e["path"] for e in result["entries"]}
        assert "src" in paths
        assert "src/a.py" in paths

    def test_search_code_finds_match(self):
        T.write_file(PROJECT, "main.py", "def hello():\n    return 'world'\n")
        result = T.search_code(PROJECT, "hello")
        assert result["ok"] is True
        assert result["count"] >= 1
        assert any("main.py" in m["path"] for m in result["matches"])

    def test_search_code_empty_query_errors(self):
        result = T.search_code(PROJECT, "")
        assert result["ok"] is False


# ── run_terminal allowlist ────────────────────────────────────────────────

class TestRunTerminalAllowlist:
    def test_safe_command_runs(self):
        result = T.run_terminal(PROJECT, "echo hello-sandbox")
        assert result["ok"] is True
        assert "hello-sandbox" in result["stdout"]

    def test_unknown_command_is_blocked(self):
        result = T.run_terminal(PROJECT, "totally_unknown_binary --flag")
        assert result["ok"] is False
        assert "not on the allowlist" in result["error"]

    def test_always_blocked_command_rejected_even_with_approval(self):
        result = T.run_terminal(PROJECT, "sudo rm -rf /", approved=True)
        assert result["ok"] is False
        assert "never allowed" in result["error"]

    def test_rm_requires_approval(self):
        T.write_file(PROJECT, "junk.txt", "delete me")
        denied = T.run_terminal(PROJECT, "rm junk.txt", approved=False)
        assert denied["ok"] is False
        assert denied.get("requires_approval") is True

        approved = T.run_terminal(PROJECT, "rm junk.txt", approved=True)
        assert approved["ok"] is True

    def test_pip_install_requires_approval(self):
        result = T.run_terminal(PROJECT, "pip install requests", approved=False)
        assert result["ok"] is False
        assert result.get("requires_approval") is True

    def test_command_chaining_checks_every_segment(self):
        # second segment (rm) should trigger approval requirement
        result = T.run_terminal(PROJECT, "echo ok && rm -rf somefile", approved=False)
        assert result["ok"] is False


# ── git_status / git_commit ───────────────────────────────────────────────

class TestGit:
    def test_git_status_initializes_repo(self):
        result = T.git_status(PROJECT)
        assert result["ok"] is True
        assert (T.WORKSPACE_ROOT / PROJECT / ".git").exists()

    def test_git_commit_creates_commit(self):
        T.write_file(PROJECT, "README.md", "# Test project\n")
        result = T.git_commit(PROJECT, "initial commit")
        assert result["ok"] is True
        assert result["nothing_to_commit"] is False
        assert result["commit_sha"] is not None

    def test_git_commit_nothing_to_commit(self):
        T.write_file(PROJECT, "README.md", "# Test project\n")
        T.git_commit(PROJECT, "first")
        second = T.git_commit(PROJECT, "second, but nothing changed")
        assert second["ok"] is True
        assert second["nothing_to_commit"] is True

    def test_git_commit_empty_message_rejected(self):
        result = T.git_commit(PROJECT, "   ")
        assert result["ok"] is False


# ── run_tests ──────────────────────────────────────────────────────────────

class TestRunTests:
    def test_run_tests_against_real_pytest_file(self):
        T.write_file(PROJECT, "tests/test_sample.py", "def test_ok():\n    assert 1 + 1 == 2\n")
        result = T.run_tests(PROJECT, suite="tests/test_sample.py")
        assert result["ok"] is True
        assert result["passed"] is True

    def test_run_tests_reports_failure(self):
        T.write_file(PROJECT, "tests/test_fail.py", "def test_bad():\n    assert 1 == 2\n")
        result = T.run_tests(PROJECT, suite="tests/test_fail.py")
        assert result["ok"] is True
        assert result["passed"] is False


# ── ProjectTools wrapper ───────────────────────────────────────────────────

class TestProjectToolsWrapper:
    def test_bound_methods_match_module_functions(self):
        pt = T.ProjectTools(PROJECT)
        pt.write_file("bound.txt", "via wrapper")
        result = pt.read_file("bound.txt")
        assert result["ok"] is True
        assert result["content"] == "via wrapper"

    def test_results_are_json_serializable(self):
        pt = T.ProjectTools(PROJECT)
        pt.write_file("x.txt", "y")
        result = pt.list_dir(".")
        json.dumps(result)  # must not raise
