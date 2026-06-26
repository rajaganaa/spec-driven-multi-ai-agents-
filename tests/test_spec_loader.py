"""
tests/test_spec_loader.py — Part C unit tests

Focus areas:
  1. load_spec() parses the real feature/task markdown templates
     correctly (sections, checklists, file lists, scalars).
  2. build_agent_context() respects the max-files / token-budget limits
     and truncates/skips gracefully when context would blow the budget.
  3. update_board_status() creates + updates entries in status/board.json,
     including the "create if missing" case and isolation between
     independently-tracked tasks.

All three test classes use the `fake_hub` fixture, which monkeypatches
spec_loader's module-level path constants (ROOT, SPECS_DIR, TASKS_DIR,
BOARD_PATH, META_PATH) to a throwaway tmp_path layout — so these tests
never touch the real specs/ or status/board.json.

hub/tools/tools.py is a separate module with its own WORKSPACE_ROOT that
is NOT affected by that monkeypatching (by design: workspace/projects/
is meant to be a real, shared sandbox). Tests that need a project-level
context file use a disposable real project id and clean it up after,
the same way tests/test_tools.py does for its own sandbox tests.
"""

import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from hub.memory import spec_loader as S  # noqa: E402
from hub.tools import tools as TOOLS  # noqa: E402


TEST_PROJECT_ID = "spec-loader-test-project"

FEATURE_MD = """# F01: Example Feature

## Goal
One sentence: what this feature delivers.

## Acceptance Criteria
- [ ] Criterion 1
- [x] Criterion 2
- [ ] All tests pass: `pytest tests/test_<feature>.py`

## Files Likely Touched
- `src/<module>/<file>.py`
- `tests/test_<feature>.py`

## Dependencies
- F00: project scaffold (must be done first)

## Assigned Lead
feature-lead

## Status
planning
"""

TASK_MD = """# T01: Example Task

## Feature
F01

## Role
coder   # explorer | coder | tester | reviewer

## Goal
One sentence: what this task implements.

## Context Files (max 5)
- `specs/features/F01-example.md`
- `src/module/file.py`

## Instructions
Step-by-step instructions for the specialist agent.
1. Read the context files listed above.
2. Implement X by doing Y.
3. Write unit tests in `tests/test_x.py`.

## Acceptance Criteria
- [ ] File `src/module/file.py` exists and is correct.
- [ ] `pytest tests/test_x.py` passes with no errors.

## Definition of Done
- All acceptance criteria checked.
- Output: list files created/modified + test result summary.
- Blockers (if any) noted.

## Status
pending
"""


@pytest.fixture
def fake_hub(tmp_path, monkeypatch):
    """Point every spec_loader path constant at a throwaway hub layout."""
    root = tmp_path / "fake-hub"
    specs = root / "specs"
    features_dir = specs / "features"
    tasks_dir = specs / "tasks"
    features_dir.mkdir(parents=True)
    tasks_dir.mkdir(parents=True)

    monkeypatch.setattr(S, "ROOT", root)
    monkeypatch.setattr(S, "SPECS_DIR", specs)
    monkeypatch.setattr(S, "FEATURES_DIR", features_dir)
    monkeypatch.setattr(S, "TASKS_DIR", tasks_dir)
    monkeypatch.setattr(S, "BOARD_PATH", root / "status" / "board.json")
    monkeypatch.setattr(S, "META_PATH", root / "project.meta.json")

    (features_dir / "F01-example.md").write_text(FEATURE_MD, encoding="utf-8")
    (tasks_dir / "T01-example.md").write_text(TASK_MD, encoding="utf-8")
    (root / "project.meta.json").write_text(json.dumps({"project_id": TEST_PROJECT_ID}), encoding="utf-8")

    # hub/tools/tools.py's WORKSPACE_ROOT is real and untouched by the
    # monkeypatching above — guarantee a clean slate before and after.
    real_proj_dir = TOOLS.WORKSPACE_ROOT / TEST_PROJECT_ID
    if real_proj_dir.exists():
        shutil.rmtree(real_proj_dir)

    yield {"root": root, "features_dir": features_dir, "tasks_dir": tasks_dir}

    if real_proj_dir.exists():
        shutil.rmtree(real_proj_dir)


# ── load_spec ────────────────────────────────────────────────────────────

class TestLoadSpec:
    def test_loads_feature_spec_correctly(self, fake_hub):
        result = S.load_spec("specs/features/F01-example.md")
        assert result["ok"] is True
        assert result["type"] == "feature"
        assert result["id"] == "F01"
        assert result["title"] == "Example Feature"
        assert result["goal"].startswith("One sentence")
        assert result["status"] == "planning"
        assert result["assigned_lead"] == "feature-lead"

        assert len(result["acceptance_criteria"]) == 3
        assert result["acceptance_criteria"][0] == {"text": "Criterion 1", "done": False}
        assert result["acceptance_criteria"][1] == {"text": "Criterion 2", "done": True}

        assert result["files_likely_touched"] == ["src/<module>/<file>.py", "tests/test_<feature>.py"]
        assert result["dependencies"] == ["F00: project scaffold (must be done first)"]

    def test_loads_task_spec_correctly(self, fake_hub):
        result = S.load_spec("specs/tasks/T01-example.md")
        assert result["ok"] is True
        assert result["type"] == "task"
        assert result["id"] == "T01"
        assert result["title"] == "Example Task"
        assert result["feature"] == "F01"
        assert result["role"] == "coder"
        assert result["status"] == "pending"
        assert result["context_files"] == ["specs/features/F01-example.md", "src/module/file.py"]
        assert len(result["acceptance_criteria"]) == 2
        assert len(result["definition_of_done"]) == 3
        assert "Step-by-step" in result["instructions"]

    def test_missing_file_returns_error(self, fake_hub):
        result = S.load_spec("specs/tasks/does-not-exist.md")
        assert result["ok"] is False
        assert "not found" in result["error"].lower()

    def test_invalid_json_spec_returns_error(self, fake_hub, tmp_path):
        bad = fake_hub["tasks_dir"] / "bad.json"
        bad.write_text("{not valid json", encoding="utf-8")
        result = S.load_spec(str(bad))
        assert result["ok"] is False
        assert "json" in result["error"].lower()

    def test_unknown_header_is_captured_not_dropped(self, fake_hub):
        custom = FEATURE_MD + "\n## Notes From Reviewer\nWatch out for X.\n"
        path = fake_hub["features_dir"] / "F02-custom.md"
        path.write_text(custom, encoding="utf-8")
        result = S.load_spec("specs/features/F02-custom.md")
        assert result["ok"] is True
        assert "notes_from_reviewer" in result
        assert "Watch out for X" in result["notes_from_reviewer"]


# ── build_agent_context ────────────────────────────────────────────────────

class TestBuildAgentContext:
    def test_loads_task_and_context_files(self, fake_hub):
        TOOLS.write_file(TEST_PROJECT_ID, "src/module/file.py", "print('hello')\n")

        result = S.build_agent_context("T01")
        assert result["ok"] is True
        assert result["task_id"] == "T01"
        assert result["feature"] == "F01"
        assert result["project_id"] == TEST_PROJECT_ID

        by_path = {cf["path"]: cf for cf in result["context_files"]}
        assert by_path["specs/features/F01-example.md"]["included"] is True
        assert "Example Feature" in by_path["specs/features/F01-example.md"]["content"]
        assert by_path["src/module/file.py"]["included"] is True
        assert "print('hello')" in by_path["src/module/file.py"]["content"]

        assert result["max_files"] == S.MAX_CONTEXT_FILES
        assert result["context_files_overflow"] is False
        assert "## Context File: src/module/file.py" in result["prompt"]

    def test_unknown_task_id_returns_error(self, fake_hub):
        result = S.build_agent_context("T99")
        assert result["ok"] is False
        assert "no task spec" in result["error"].lower()

    def test_missing_context_file_is_reported_not_fatal(self, fake_hub):
        # src/module/file.py was never created in the project workspace.
        result = S.build_agent_context("T01")
        assert result["ok"] is True
        by_path = {cf["path"]: cf for cf in result["context_files"]}
        assert by_path["src/module/file.py"]["included"] is False
        assert by_path["src/module/file.py"]["error"]

    def test_budget_truncation_when_files_exceed_token_limit(self, fake_hub):
        TOOLS.write_file(TEST_PROJECT_ID, "src/module/file.py", "x" * 4000)

        result = S.build_agent_context("T01", max_tokens=50)
        assert result["ok"] is True
        assert result["total_tokens_estimate"] <= 50

        by_path = {cf["path"]: cf for cf in result["context_files"]}
        first = by_path["specs/features/F01-example.md"]
        second = by_path["src/module/file.py"]
        # With a 50-token budget, the first file alone can't fully fit,
        # so it gets truncated and the second is skipped entirely.
        assert first["truncated"] is True
        assert second["included"] is False
        assert "skipped" in second["error"].lower()

    def test_max_files_caps_context_list(self, fake_hub):
        many_files_md = TASK_MD.replace(
            "- `specs/features/F01-example.md`\n- `src/module/file.py`\n",
            "".join(f"- `src/f{i}.py`\n" for i in range(8)),
        )
        (fake_hub["tasks_dir"] / "T01-example.md").write_text(many_files_md, encoding="utf-8")

        result = S.build_agent_context("T01", max_files=5)
        assert result["ok"] is True
        assert result["context_files_overflow"] is True
        assert len(result["context_files"]) == 5

    def test_finds_nested_task_spec_layout(self, fake_hub):
        nested_dir = fake_hub["tasks_dir"] / "F01-example"
        nested_dir.mkdir()
        (nested_dir / "T02-nested.md").write_text(
            TASK_MD.replace("# T01: Example Task", "# T02: Nested Task"), encoding="utf-8",
        )
        result = S.build_agent_context("T02")
        assert result["ok"] is True
        assert result["task_id"] == "T02"


# ── update_board_status ─────────────────────────────────────────────────────

class TestUpdateBoardStatus:
    def test_creates_board_and_entry_when_missing(self, fake_hub):
        result = S.update_board_status("T01", "in_progress", agent="coder")
        assert result["ok"] is True
        assert result["created"] is True
        assert result["task"]["id"] == "T01"
        assert result["task"]["status"] == "in_progress"
        assert result["task"]["agent"] == "coder"
        assert result["task"]["feature"] == "F01"  # inferred from the task spec

        board = json.loads((fake_hub["root"] / "status" / "board.json").read_text())
        assert len(board["tasks"]) == 1
        assert board["updated_at"] != ""

    def test_updates_existing_entry_without_wiping_unprovided_fields(self, fake_hub):
        S.update_board_status("T01", "in_progress", agent="coder")
        result = S.update_board_status("T01", "done", commit="abc123")
        assert result["ok"] is True
        assert result["created"] is False
        assert result["task"]["status"] == "done"
        assert result["task"]["commit"] == "abc123"
        assert result["task"]["agent"] == "coder"  # preserved, not overwritten by the 2nd call

        board = json.loads((fake_hub["root"] / "status" / "board.json").read_text())
        assert len(board["tasks"]) == 1

    def test_concurrent_task_isolation(self, fake_hub):
        (fake_hub["tasks_dir"] / "T02-example.md").write_text(
            TASK_MD.replace("# T01: Example Task", "# T02: Second Task"), encoding="utf-8",
        )

        S.update_board_status("T01", "in_progress", agent="coder")
        S.update_board_status("T02", "in_progress", agent="tester")
        S.update_board_status("T01", "done", commit="abc123")

        board = json.loads((fake_hub["root"] / "status" / "board.json").read_text())
        by_id = {t["id"]: t for t in board["tasks"]}
        assert by_id["T01"]["status"] == "done"
        assert by_id["T01"]["commit"] == "abc123"
        assert by_id["T02"]["status"] == "in_progress"
        assert by_id["T02"]["commit"] is None
        assert by_id["T02"]["agent"] == "tester"

    def test_invalid_task_id_rejected(self, fake_hub):
        result = S.update_board_status("", "done")
        assert result["ok"] is False

    def test_invalid_status_rejected(self, fake_hub):
        result = S.update_board_status("T01", "")
        assert result["ok"] is False

    def test_corrupted_board_file_returns_error(self, fake_hub):
        board_path = fake_hub["root"] / "status" / "board.json"
        board_path.parent.mkdir(parents=True, exist_ok=True)
        board_path.write_text("{not valid json", encoding="utf-8")
        result = S.update_board_status("T01", "in_progress")
        assert result["ok"] is False
        assert "corrupt" in result["error"].lower()

    def test_results_are_json_serializable(self, fake_hub):
        result = S.update_board_status("T01", "in_progress", agent="coder")
        json.dumps(result)  # must not raise
