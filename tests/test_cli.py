"""
tests/test_cli.py — Part E unit tests for cli/main.py

The underlying agent/runner functions (Orchestrator, Feature Lead,
task runner) are already exercised end-to-end with real ADK machinery
in tests/test_agents_planning.py and tests/test_task_runner.py. Here,
those functions are mocked with realistic return shapes so these tests
isolate and verify what's actually cli/main.py's own job: command
wiring, output formatting (including the rich-markup escaping fix for
goals/errors that may contain literal brackets), and exit codes.
"""

import json
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cli import main as cli_main  # noqa: E402


@pytest.fixture
def fake_project(tmp_path, monkeypatch):
    """Redirect cli/main.py's META_PATH/BOARD_PATH at a throwaway
    project so these tests never touch the real project.meta.json or
    status/board.json."""
    meta_path = tmp_path / "project.meta.json"
    board_path = tmp_path / "status" / "board.json"
    board_path.parent.mkdir(parents=True)

    monkeypatch.setattr(cli_main, "META_PATH", meta_path)
    monkeypatch.setattr(cli_main, "BOARD_PATH", board_path)

    return {"meta_path": meta_path, "board_path": board_path}


def _write_meta(meta_path: Path, **overrides) -> dict:
    meta = {
        "project_id": "demo-project",
        "goal": "Build a hello world FastAPI app",
        "stack": ["python", "fastapi"],
        "constraints": [],
        "status": "planning",
        "created_at": "2026-06-24",
        "updated_at": "2026-06-24",
        "features": [],
        "notes": "",
    }
    meta.update(overrides)
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def _write_board(board_path: Path, tasks: list) -> None:
    board_path.write_text(
        json.dumps({"project_id": "demo-project", "updated_at": "", "tasks": tasks}, indent=2), encoding="utf-8"
    )


# ── new ───────────────────────────────────────────────────────────────────

class TestNewCommand:
    def test_creates_meta_and_board(self, fake_project):
        runner = CliRunner()
        result = runner.invoke(cli_main.cli, ["new", "Build a [REST] API", "--stack", "python,django"])

        assert result.exit_code == 0
        assert "Build a [REST] API" in result.output  # bracket survives — escaping fix

        meta = json.loads(fake_project["meta_path"].read_text())
        assert meta["goal"] == "Build a [REST] API"
        assert meta["stack"] == ["python", "django"]

        board = json.loads(fake_project["board_path"].read_text())
        assert board["tasks"] == []


# ── plan ──────────────────────────────────────────────────────────────────

class TestPlanCommand:
    def test_runs_orchestrator_then_feature_lead_per_feature(self, fake_project, monkeypatch):
        _write_meta(fake_project["meta_path"])

        def fake_run_orchestrator(goal, project_id=None, model=None, max_features=None):
            return {
                "ok": True, "error": None, "project_id": project_id, "goal": goal,
                "project_plan_path": "specs/00-project-plan.md",
                "feature_spec_paths": ["specs/features/F01-api.md", "specs/features/F02-tests.md"],
                "feature_ids": ["F01", "F02"], "feature_count": 2, "features_overflow": False,
                "summary": "Build the API and tests.",
            }

        def fake_run_feature_lead(feature_spec_path, project_id=None, model=None, max_tasks=None):
            fid = "F01" if "F01" in feature_spec_path else "F02"
            return {
                "ok": True, "error": None, "project_id": project_id, "feature": fid,
                "feature_spec_path": feature_spec_path,
                "task_spec_paths": [f"specs/tasks/{fid}/T01-x.md"],
                "task_ids": ["T01"], "task_count": 1, "tasks_overflow": False,
                "board_updates": [{"task_id": "T01", "ok": True, "error": None}],
            }

        monkeypatch.setattr(cli_main.orchestrator, "run_orchestrator", fake_run_orchestrator)
        monkeypatch.setattr(cli_main.feature_lead, "run_feature_lead", fake_run_feature_lead)

        runner = CliRunner()
        result = runner.invoke(cli_main.cli, ["plan"])

        assert result.exit_code == 0
        assert "F01" in result.output and "F02" in result.output
        assert "2 task(s) ready" in result.output

    def test_orchestrator_failure_exits_nonzero_and_escapes_error(self, fake_project, monkeypatch):
        _write_meta(fake_project["meta_path"])

        def fake_run_orchestrator(goal, project_id=None, model=None, max_features=None):
            return {"ok": False, "error": "schema validation failed: [type=missing, loc=('features',)]"}

        monkeypatch.setattr(cli_main.orchestrator, "run_orchestrator", fake_run_orchestrator)

        runner = CliRunner()
        result = runner.invoke(cli_main.cli, ["plan"])

        assert result.exit_code == 1
        assert "[type=missing" in result.output  # literal brackets survive — escaping fix
        assert "Orchestrator failed" in result.output

    def test_feature_lead_failure_on_one_feature_still_reports_and_exits_nonzero(self, fake_project, monkeypatch):
        _write_meta(fake_project["meta_path"])

        def fake_run_orchestrator(goal, project_id=None, model=None, max_features=None):
            return {
                "ok": True, "error": None, "project_id": project_id, "goal": goal,
                "project_plan_path": "specs/00-project-plan.md",
                "feature_spec_paths": ["specs/features/F01-api.md"],
                "feature_ids": ["F01"], "feature_count": 1, "features_overflow": False,
                "summary": "x",
            }

        def fake_run_feature_lead(feature_spec_path, project_id=None, model=None, max_tasks=None):
            return {"ok": False, "error": "Feature Lead output failed schema validation"}

        monkeypatch.setattr(cli_main.orchestrator, "run_orchestrator", fake_run_orchestrator)
        monkeypatch.setattr(cli_main.feature_lead, "run_feature_lead", fake_run_feature_lead)

        runner = CliRunner()
        result = runner.invoke(cli_main.cli, ["plan"])

        assert result.exit_code == 1
        assert "F01" in result.output
        assert "schema validation" in result.output


# ── run ───────────────────────────────────────────────────────────────────

class TestRunCommand:
    def test_run_single_task_success(self, fake_project, monkeypatch):
        _write_meta(fake_project["meta_path"])
        _write_board(fake_project["board_path"], [{"id": "T01", "feature": "F01", "status": "pending", "agent": None, "commit": None}])

        def fake_run_task(task_id, project_id=None, model=None, max_turns=None, max_retries=None):
            return {
                "ok": True, "error": None, "task_id": task_id, "role": "coder", "status": "done",
                "attempts": [{"attempt": 1, "success": True, "reason": "ok", "tool_call_count": 1}],
                "attempt_count": 1, "final_text": "Done.", "tool_calls": [], "commit_sha": "abc123",
            }

        monkeypatch.setattr(cli_main.task_runner, "run_task", fake_run_task)

        runner = CliRunner()
        result = runner.invoke(cli_main.cli, ["run", "--task", "T01"])

        assert result.exit_code == 0
        assert "T01" in result.output
        assert "abc123" in result.output

    def test_run_single_task_failure_exits_nonzero(self, fake_project, monkeypatch):
        _write_meta(fake_project["meta_path"])

        def fake_run_task(task_id, project_id=None, model=None, max_turns=None, max_retries=None):
            return {"ok": False, "error": "No task spec found for task_id: T99", "task_id": task_id}

        monkeypatch.setattr(cli_main.task_runner, "run_task", fake_run_task)

        runner = CliRunner()
        result = runner.invoke(cli_main.cli, ["run", "--task", "T99"])

        assert result.exit_code == 1
        assert "T99" in result.output

    def test_run_all_pending_aggregates_and_reports(self, fake_project, monkeypatch):
        _write_meta(fake_project["meta_path"])
        _write_board(fake_project["board_path"], [
            {"id": "T01", "feature": "F01", "status": "pending", "agent": None, "commit": None},
            {"id": "T02", "feature": "F01", "status": "pending", "agent": None, "commit": None},
        ])

        def fake_run_pending_tasks(project_id=None, model=None, max_turns=None, max_retries=None):
            return {
                "ok": True, "error": None, "project_id": project_id, "task_count": 2,
                "done_count": 1, "failed_count": 1,
                "results": [
                    {"ok": True, "task_id": "T01", "role": "coder", "attempt_count": 1, "commit_sha": "abc123"},
                    {"ok": False, "task_id": "T02", "role": "tester", "error": "tests failed: [assert x == y]"},
                ],
            }

        monkeypatch.setattr(cli_main.task_runner, "run_pending_tasks", fake_run_pending_tasks)

        runner = CliRunner()
        result = runner.invoke(cli_main.cli, ["run"])

        assert result.exit_code == 1  # at least one task failed
        assert "1 done, 1 failed" in result.output
        assert "[assert x == y]" in result.output  # literal brackets survive — escaping fix

    def test_run_with_no_pending_tasks_is_a_noop(self, fake_project):
        _write_meta(fake_project["meta_path"])
        _write_board(fake_project["board_path"], [])

        runner = CliRunner()
        result = runner.invoke(cli_main.cli, ["run"])

        assert result.exit_code == 0
        assert "Nothing to run" in result.output


# ── status ────────────────────────────────────────────────────────────────

class TestStatusCommand:
    def test_renders_table_with_goal_containing_brackets(self, fake_project):
        _write_meta(fake_project["meta_path"], goal="Ship the [v2] API")
        _write_board(fake_project["board_path"], [
            {"id": "T01", "feature": "F01", "status": "done", "agent": "coder", "commit": "abc123"},
            {"id": "T02", "feature": "F01", "status": "failed", "agent": "tester", "commit": None},
        ])

        runner = CliRunner()
        result = runner.invoke(cli_main.cli, ["status"])

        assert result.exit_code == 0
        assert "[v2]" in result.output  # literal brackets survive — escaping fix
        assert "T01" in result.output and "T02" in result.output

    def test_no_tasks_shows_hint(self, fake_project):
        _write_meta(fake_project["meta_path"])
        _write_board(fake_project["board_path"], [])

        runner = CliRunner()
        result = runner.invoke(cli_main.cli, ["status"])

        assert result.exit_code == 0
        assert "agent plan" in result.output

    def test_missing_project_exits_nonzero(self, fake_project):
        runner = CliRunner()
        result = runner.invoke(cli_main.cli, ["status"])
        assert result.exit_code != 0


# ── Full pipeline integration: new -> plan -> run -> status ───────────────
#
# Everything below is real (file writes, git init/commit, board.json
# updates, retry logic) — only the model call itself is faked, by
# wrapping orchestrator.run_orchestrator / feature_lead.run_feature_lead /
# task_runner.run_pending_tasks to inject a shared FakeLlm regardless of
# what cli/main.py passes as `model` (it passes None, since no --model
# flag was given — CliRunner can't pass a Python object through CLI
# argv, so this is the seam used instead).

class TestFullPipelineIntegration:
    @pytest.fixture
    def isolated_hub(self, tmp_path, monkeypatch):
        root = tmp_path / "fake-hub"
        specs = root / "specs"
        features_dir = specs / "features"
        tasks_dir = specs / "tasks"
        workspace_root = root / "workspace" / "projects"
        features_dir.mkdir(parents=True)
        tasks_dir.mkdir(parents=True)
        workspace_root.mkdir(parents=True)

        from hub.memory import spec_loader as S
        from hub.tools import tools as TOOLS

        monkeypatch.setattr(TOOLS, "ROOT", root)
        monkeypatch.setattr(TOOLS, "SPECS_ROOT", specs.resolve())
        monkeypatch.setattr(TOOLS, "WORKSPACE_ROOT", workspace_root.resolve())

        monkeypatch.setattr(S, "ROOT", root)
        monkeypatch.setattr(S, "SPECS_DIR", specs)
        monkeypatch.setattr(S, "FEATURES_DIR", features_dir)
        monkeypatch.setattr(S, "TASKS_DIR", tasks_dir)
        monkeypatch.setattr(S, "BOARD_PATH", root / "status" / "board.json")
        monkeypatch.setattr(S, "META_PATH", root / "project.meta.json")

        monkeypatch.setattr(cli_main, "META_PATH", root / "project.meta.json")
        monkeypatch.setattr(cli_main, "BOARD_PATH", root / "status" / "board.json")

        return {"root": root}

    def test_new_plan_run_status_round_trip(self, isolated_hub, monkeypatch):
        from google.adk.models.llm_response import LlmResponse
        from google.genai import types

        from tests.fake_llm import FakeLlm, json_turn

        def function_call_turn(name, args):
            return LlmResponse(content=types.Content(role="model", parts=[types.Part.from_function_call(name=name, args=args)]))

        def text_turn(text):
            return LlmResponse(content=types.Content(role="model", parts=[types.Part.from_text(text=text)]))

        # 1 Orchestrator turn, 1 Feature Lead turn, then 2 Coder turns
        # (one tool call + one final reply) for the single resulting task.
        fake_model = FakeLlm(model="fake", turns=[
            json_turn({
                "goal": "Build a hello world FastAPI app",
                "summary": "Scaffold a minimal app.",
                "features": [{
                    "id": "F01", "title": "API Scaffold", "goal": "Stand up the app",
                    "acceptance_criteria": ["App runs"], "files_likely_touched": ["src/app/main.py"],
                    "dependencies": [], "assigned_lead": "feature-lead",
                }],
            }),
            json_turn({
                "feature": "F01",
                "tasks": [{
                    "id": "T01", "title": "Scaffold app", "role": "coder", "goal": "Create main.py",
                    "context_files": [], "instructions": "Create src/app/main.py.",
                    "acceptance_criteria": ["main.py exists"], "definition_of_done": ["main.py exists"],
                }],
            }),
            function_call_turn("write_file", {"path": "src/app/main.py", "content": "print('hello')\n"}),
            text_turn("Created src/app/main.py."),
        ])

        import hub.agents.feature_lead as feature_lead_mod
        import hub.agents.orchestrator as orchestrator_mod
        import hub.runner.task_runner as task_runner_mod

        real_run_orchestrator = orchestrator_mod.run_orchestrator
        real_run_feature_lead = feature_lead_mod.run_feature_lead
        real_run_pending_tasks = task_runner_mod.run_pending_tasks

        monkeypatch.setattr(
            cli_main.orchestrator, "run_orchestrator",
            lambda goal, project_id=None, model=None, max_features=None:
                real_run_orchestrator(goal, project_id=project_id, model=fake_model, max_features=max_features),
        )
        monkeypatch.setattr(
            cli_main.feature_lead, "run_feature_lead",
            lambda feature_spec_path, project_id=None, model=None, max_tasks=None:
                real_run_feature_lead(feature_spec_path, project_id=project_id, model=fake_model, max_tasks=max_tasks),
        )
        monkeypatch.setattr(
            cli_main.task_runner, "run_pending_tasks",
            lambda project_id=None, model=None, max_turns=None, max_retries=None:
                real_run_pending_tasks(project_id=project_id, model=fake_model, max_turns=max_turns, max_retries=max_retries),
        )

        runner = CliRunner()

        new_result = runner.invoke(cli_main.cli, ["new", "Build a hello world FastAPI app"])
        assert new_result.exit_code == 0

        plan_result = runner.invoke(cli_main.cli, ["plan"])
        assert plan_result.exit_code == 0, plan_result.output
        assert "F01" in plan_result.output
        assert "1 task(s) ready" in plan_result.output

        run_result = runner.invoke(cli_main.cli, ["run"])
        assert run_result.exit_code == 0, run_result.output
        assert "1 done, 0 failed" in run_result.output

        status_result = runner.invoke(cli_main.cli, ["status"])
        assert status_result.exit_code == 0
        assert "T01" in status_result.output
        assert "done" in status_result.output

        # And the file the Coder specialist actually wrote is really there.
        meta = json.loads((isolated_hub["root"] / "project.meta.json").read_text())
        written = (isolated_hub["root"] / "workspace" / "projects" / meta["project_id"] / "src" / "app" / "main.py")
        assert written.exists()
        assert written.read_text() == "print('hello')\n"
