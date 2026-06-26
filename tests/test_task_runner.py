"""
tests/test_task_runner.py — Part E unit tests (hub/runner/task_runner.py)

Drives the real specialist agents (Part E) through the real ADK Runner,
real ProjectTools (real sandboxed file writes, real git init/commit),
and real spec_loader board updates — only the model call itself is
faked (tests/fake_llm.py), so there's no network access or API key
needed, but everything else is the genuine pipeline.

The fake_hub fixture monkeypatches hub.tools.tools' ROOT/SPECS_ROOT/
WORKSPACE_ROOT and hub.memory.spec_loader's path constants to the same
tmp_path layout, so every git/file operation in these tests is fully
disposable — nothing here touches the real specs/, status/, or
workspace/projects/.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from google.adk.models.llm_response import LlmResponse  # noqa: E402
from google.genai import types  # noqa: E402

from hub.memory import spec_loader as S  # noqa: E402
from hub.runner import task_runner as R  # noqa: E402
from hub.tools import tools as TOOLS  # noqa: E402
from tests.fake_llm import FakeLlm  # noqa: E402


def make_task_md(task_id: str, role: str, title: str = "Task", feature: str = "F01") -> str:
    return (
        f"# {task_id}: {title}\n\n"
        f"## Feature\n{feature}\n\n"
        f"## Role\n{role}\n\n"
        f"## Goal\nDo the thing.\n\n"
        f"## Context Files (max 5)\n(none)\n\n"
        f"## Instructions\nDo it.\n\n"
        f"## Acceptance Criteria\n- [ ] done\n\n"
        f"## Definition of Done\n- done\n\n"
        f"## Status\npending\n"
    )


def function_call_turn(name: str, args: dict) -> LlmResponse:
    return LlmResponse(content=types.Content(role="model", parts=[types.Part.from_function_call(name=name, args=args)]))


def text_response_turn(text: str) -> LlmResponse:
    return LlmResponse(content=types.Content(role="model", parts=[types.Part.from_text(text=text)]))


@pytest.fixture
def fake_hub(tmp_path, monkeypatch):
    """Fully isolated fake hub: specs/, status/, project.meta.json, AND
    workspace/projects/ (so file writes + git commits are real but
    disposable)."""
    root = tmp_path / "fake-hub"
    specs = root / "specs"
    features_dir = specs / "features"
    tasks_dir = specs / "tasks"
    workspace_root = root / "workspace" / "projects"
    features_dir.mkdir(parents=True)
    tasks_dir.mkdir(parents=True)
    workspace_root.mkdir(parents=True)

    monkeypatch.setattr(TOOLS, "ROOT", root)
    monkeypatch.setattr(TOOLS, "SPECS_ROOT", specs.resolve())
    monkeypatch.setattr(TOOLS, "WORKSPACE_ROOT", workspace_root.resolve())

    monkeypatch.setattr(S, "ROOT", root)
    monkeypatch.setattr(S, "SPECS_DIR", specs)
    monkeypatch.setattr(S, "FEATURES_DIR", features_dir)
    monkeypatch.setattr(S, "TASKS_DIR", tasks_dir)
    monkeypatch.setattr(S, "BOARD_PATH", root / "status" / "board.json")
    monkeypatch.setattr(S, "META_PATH", root / "project.meta.json")

    (root / "project.meta.json").write_text(json.dumps({"project_id": "demo-project"}), encoding="utf-8")
    (root / "status").mkdir(parents=True, exist_ok=True)
    (root / "status" / "board.json").write_text(
        json.dumps({"project_id": "demo-project", "updated_at": "", "tasks": []}), encoding="utf-8"
    )

    return {"root": root, "tasks_dir": tasks_dir, "workspace_root": workspace_root}


# ── run_task: single task ─────────────────────────────────────────────────

class TestRunTask:
    def test_success_writes_file_commits_and_marks_done(self, fake_hub):
        (fake_hub["tasks_dir"] / "T01-task.md").write_text(make_task_md("T01", "coder"), encoding="utf-8")
        fake_model = FakeLlm(model="fake", turns=[
            function_call_turn("write_file", {"path": "src/x.py", "content": "print(1)\n"}),
            text_response_turn("Done."),
        ])

        result = R.run_task("T01", project_id="demo-project", model=fake_model)

        assert result["ok"] is True
        assert result["status"] == "done"
        assert result["role"] == "coder"
        assert result["attempt_count"] == 1
        assert result["commit_sha"]

        board = json.loads((fake_hub["root"] / "status" / "board.json").read_text())
        by_id = {t["id"]: t for t in board["tasks"]}
        assert by_id["T01"]["status"] == "done"
        assert by_id["T01"]["commit"] == result["commit_sha"]
        assert by_id["T01"]["agent"] == "coder"

        written = TOOLS.read_file("demo-project", "src/x.py")
        assert written["ok"] is True
        assert written["content"] == "print(1)\n"

    def test_retries_after_tool_failure_then_succeeds(self, fake_hub):
        (fake_hub["tasks_dir"] / "T01-task.md").write_text(make_task_md("T01", "coder"), encoding="utf-8")
        fake_model = FakeLlm(model="fake", turns=[
            function_call_turn("write_file", {"path": "../../escape.py", "content": "x"}),  # blocked by the sandbox
            text_response_turn("Wrote it."),
            function_call_turn("write_file", {"path": "src/x.py", "content": "ok"}),
            text_response_turn("Fixed and wrote it."),
        ])

        result = R.run_task("T01", project_id="demo-project", model=fake_model, max_retries=3)

        assert result["ok"] is True
        assert result["attempt_count"] == 2
        assert result["attempts"][0]["success"] is False
        assert result["attempts"][1]["success"] is True

    def test_exhausts_retries_then_marks_failed(self, fake_hub):
        (fake_hub["tasks_dir"] / "T01-task.md").write_text(make_task_md("T01", "coder"), encoding="utf-8")
        bad_call = function_call_turn("write_file", {"path": "../escape.py", "content": "x"})
        bad_final = text_response_turn("Wrote it.")
        fake_model = FakeLlm(model="fake", turns=[bad_call, bad_final, bad_call, bad_final])

        result = R.run_task("T01", project_id="demo-project", model=fake_model, max_retries=2)

        assert result["ok"] is False
        assert result["status"] == "failed"
        assert result["attempt_count"] == 2

        board = json.loads((fake_hub["root"] / "status" / "board.json").read_text())
        by_id = {t["id"]: t for t in board["tasks"]}
        assert by_id["T01"]["status"] == "failed"
        assert by_id["T01"]["commit"] is None

    def test_tester_role_with_no_test_run_counts_as_failure(self, fake_hub):
        (fake_hub["tasks_dir"] / "T02-task.md").write_text(make_task_md("T02", "tester"), encoding="utf-8")
        fake_model = FakeLlm(model="fake", turns=[text_response_turn("Looks fine to me.")])

        result = R.run_task("T02", project_id="demo-project", model=fake_model, max_retries=1)

        assert result["ok"] is False
        assert "verified" in result["error"].lower()

    def test_tester_role_with_failing_tests_counts_as_failure(self, fake_hub):
        (fake_hub["tasks_dir"] / "T02-task.md").write_text(make_task_md("T02", "tester"), encoding="utf-8")
        fake_model = FakeLlm(model="fake", turns=[
            function_call_turn("run_tests", {"suite": "tests/"}),
            text_response_turn("Tests failed."),
        ])

        result = R.run_task("T02", project_id="demo-project", model=fake_model, max_retries=1)

        # run_tests succeeds as a *tool call* (ok=True) but reports passed=False
        # because there's no real test suite in this sandbox — either way,
        # a non-passing/failing test tool result must not be marked done.
        assert result["ok"] is False

    def test_unknown_role_returns_error(self, fake_hub):
        (fake_hub["tasks_dir"] / "T03-task.md").write_text(make_task_md("T03", "designer"), encoding="utf-8")
        result = R.run_task("T03", project_id="demo-project")
        assert result["ok"] is False

    def test_missing_task_spec_returns_error(self, fake_hub):
        result = R.run_task("T99", project_id="demo-project")
        assert result["ok"] is False

    def test_attempt_log_is_persisted(self, fake_hub):
        (fake_hub["tasks_dir"] / "T01-task.md").write_text(make_task_md("T01", "coder"), encoding="utf-8")
        fake_model = FakeLlm(model="fake", turns=[
            function_call_turn("write_file", {"path": "src/x.py", "content": "ok"}),
            text_response_turn("Done."),
        ])

        R.run_task("T01", project_id="demo-project", model=fake_model)

        log_path = fake_hub["workspace_root"] / "demo-project" / ".agent_logs" / "T01" / "attempt-1.json"
        assert log_path.exists()
        log = json.loads(log_path.read_text())
        assert log["success"] is True
        assert log["role"] == "coder"

    def test_result_is_json_serializable(self, fake_hub):
        (fake_hub["tasks_dir"] / "T01-task.md").write_text(make_task_md("T01", "coder"), encoding="utf-8")
        fake_model = FakeLlm(model="fake", turns=[
            function_call_turn("write_file", {"path": "src/x.py", "content": "ok"}),
            text_response_turn("Done."),
        ])
        result = R.run_task("T01", project_id="demo-project", model=fake_model)
        json.dumps(result)  # must not raise


# ── run_pending_tasks: the whole board ──────────────────────────────────────

class TestRunPendingTasks:
    def test_runs_every_pending_task_and_updates_board(self, fake_hub):
        (fake_hub["tasks_dir"] / "T01-task.md").write_text(make_task_md("T01", "coder"), encoding="utf-8")
        (fake_hub["tasks_dir"] / "T02-task.md").write_text(make_task_md("T02", "explorer"), encoding="utf-8")

        board_path = fake_hub["root"] / "status" / "board.json"
        board_path.write_text(json.dumps({
            "project_id": "demo-project", "updated_at": "",
            "tasks": [
                {"id": "T01", "feature": "F01", "status": "pending", "agent": None, "commit": None},
                {"id": "T02", "feature": "F01", "status": "pending", "agent": None, "commit": None},
            ],
        }), encoding="utf-8")

        fake_model = FakeLlm(model="fake", turns=[
            function_call_turn("write_file", {"path": "src/x.py", "content": "ok"}),
            text_response_turn("Done."),
            text_response_turn("Found nothing relevant."),
        ])

        result = R.run_pending_tasks(project_id="demo-project", model=fake_model)

        assert result["ok"] is True
        assert result["task_count"] == 2
        assert result["done_count"] == 2
        assert result["failed_count"] == 0

        board = json.loads(board_path.read_text())
        statuses = {t["id"]: t["status"] for t in board["tasks"]}
        assert statuses == {"T01": "done", "T02": "done"}

    def test_no_pending_tasks_returns_empty_summary(self, fake_hub):
        result = R.run_pending_tasks(project_id="demo-project")
        assert result["ok"] is True
        assert result["task_count"] == 0
