"""
tests/test_agents_planning.py — Part D unit tests (Orchestrator, Feature Lead)

These tests drive the *real* google-adk Runner/LlmAgent/session-service
stack end to end, using tests/fake_llm.py in place of a live Gemini call
(no network access, no API key). They confirm:

  1. run_orchestrator() turns a goal into a real, parseable
     specs/00-project-plan.md + specs/features/F*.md, respecting
     max_features and resolving project_id from project.meta.json
     when not given explicitly.
  2. run_feature_lead() turns one feature spec into real, parseable
     specs/tasks/<feature>/T*.md files, registers each as "pending" on
     status/board.json, and respects max_tasks.
  3. Structured-output schema mismatches are reported as ok=False
     errors, not raised as exceptions.

All file I/O is redirected into a tmp_path fake hub via monkeypatch on
hub.tools.tools and hub.memory.spec_loader's module-level path
constants, so these tests never touch the real specs/ or status/.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from hub.agents import feature_lead as F  # noqa: E402
from hub.agents import orchestrator as O  # noqa: E402
from hub.memory import spec_loader as S  # noqa: E402
from hub.tools import tools as TOOLS  # noqa: E402
from tests.fake_llm import FakeLlm, json_turn  # noqa: E402


FEATURE_MD = """# F01: API Scaffold

## Goal
Stand up a FastAPI app with a health endpoint.

## Acceptance Criteria
- [ ] GET /health returns 200

## Files Likely Touched
- `src/app/main.py`

## Dependencies
(none)

## Assigned Lead
feature-lead

## Status
planning
"""


@pytest.fixture
def fake_hub(tmp_path, monkeypatch):
    """Redirect both tools.py's specs/ sandbox and spec_loader.py's path
    constants at the same throwaway hub layout."""
    root = tmp_path / "fake-hub"
    specs = root / "specs"
    features_dir = specs / "features"
    tasks_dir = specs / "tasks"
    features_dir.mkdir(parents=True)
    tasks_dir.mkdir(parents=True)

    monkeypatch.setattr(TOOLS, "ROOT", root)
    monkeypatch.setattr(TOOLS, "SPECS_ROOT", specs.resolve())

    monkeypatch.setattr(S, "ROOT", root)
    monkeypatch.setattr(S, "SPECS_DIR", specs)
    monkeypatch.setattr(S, "FEATURES_DIR", features_dir)
    monkeypatch.setattr(S, "TASKS_DIR", tasks_dir)
    monkeypatch.setattr(S, "BOARD_PATH", root / "status" / "board.json")
    monkeypatch.setattr(S, "META_PATH", root / "project.meta.json")

    (root / "project.meta.json").write_text(
        json.dumps({
            "project_id": "demo-project",
            "stack": ["python", "fastapi"],
            "constraints": ["no real PHI in dev"],
        }),
        encoding="utf-8",
    )

    return {"root": root, "specs": specs, "features_dir": features_dir, "tasks_dir": tasks_dir}


# ── Orchestrator ─────────────────────────────────────────────────────────

class TestOrchestrator:
    def test_writes_plan_and_feature_specs(self, fake_hub):
        plan_json = {
            "goal": "Build a hello world FastAPI app",
            "summary": "Scaffold a minimal FastAPI app with a health endpoint and tests.",
            "features": [
                {
                    "id": "F01", "title": "API Scaffold",
                    "goal": "Stand up a FastAPI app with a health endpoint",
                    "acceptance_criteria": ["GET /health returns 200", "App runs via uvicorn"],
                    "files_likely_touched": ["src/app/main.py", "tests/test_health.py"],
                    "dependencies": [], "assigned_lead": "feature-lead",
                },
                {
                    "id": "F02", "title": "Tests",
                    "goal": "Add a basic test suite",
                    "acceptance_criteria": ["pytest passes"],
                    "files_likely_touched": ["tests/test_health.py"],
                    "dependencies": ["F01"], "assigned_lead": "feature-lead",
                },
            ],
        }
        fake_model = FakeLlm(model="fake", turns=[json_turn(plan_json)])

        result = O.run_orchestrator("Build a hello world FastAPI app", project_id="demo-project", model=fake_model)

        assert result["ok"] is True
        assert result["project_id"] == "demo-project"
        assert result["feature_count"] == 2
        assert result["feature_ids"] == ["F01", "F02"]
        assert result["features_overflow"] is False

        plan_path = fake_hub["root"] / "specs" / "00-project-plan.md"
        assert plan_path.exists()
        assert "F01" in plan_path.read_text()

        f01 = S.load_spec("specs/features/F01-api-scaffold.md")
        assert f01["ok"] is True
        assert f01["type"] == "feature"
        assert f01["id"] == "F01"
        assert f01["dependencies"] == []

        f02 = S.load_spec("specs/features/F02-tests.md")
        assert f02["ok"] is True
        assert f02["dependencies"] == ["F01"]

    def test_empty_goal_rejected(self, fake_hub):
        result = O.run_orchestrator("   ", project_id="demo-project")
        assert result["ok"] is False

    def test_max_features_caps_and_flags_overflow(self, fake_hub):
        features = [
            {
                "id": f"F0{i}", "title": f"Feature {i}", "goal": f"Goal {i}",
                "acceptance_criteria": [f"Criterion {i}"],
                "files_likely_touched": [], "dependencies": [], "assigned_lead": "feature-lead",
            }
            for i in range(1, 10)
        ]
        fake_model = FakeLlm(model="fake", turns=[json_turn({"goal": "Big project", "summary": "Many features.", "features": features})])

        result = O.run_orchestrator("Big project", project_id="demo-project", model=fake_model, max_features=5)
        assert result["ok"] is True
        assert result["feature_count"] == 5
        assert result["features_overflow"] is True

    def test_invalid_structured_output_returns_error_not_exception(self, fake_hub):
        # Missing the required 'features' key entirely.
        fake_model = FakeLlm(model="fake", turns=[json_turn({"goal": "x", "summary": "y"})])
        result = O.run_orchestrator("x", project_id="demo-project", model=fake_model)
        assert result["ok"] is False
        assert "schema" in result["error"].lower() or "validation" in result["error"].lower()

    def test_uses_active_project_id_when_not_given(self, fake_hub):
        plan_json = {
            "goal": "X", "summary": "Y",
            "features": [{
                "id": "F01", "title": "One", "goal": "g",
                "acceptance_criteria": ["c"], "files_likely_touched": [], "dependencies": [], "assigned_lead": "feature-lead",
            }],
        }
        fake_model = FakeLlm(model="fake", turns=[json_turn(plan_json)])
        result = O.run_orchestrator("X", model=fake_model)  # no project_id passed
        assert result["ok"] is True
        assert result["project_id"] == "demo-project"

    def test_result_is_json_serializable(self, fake_hub):
        plan_json = {
            "goal": "X", "summary": "Y",
            "features": [{
                "id": "F01", "title": "One", "goal": "g",
                "acceptance_criteria": ["c"], "files_likely_touched": [], "dependencies": [], "assigned_lead": "feature-lead",
            }],
        }
        fake_model = FakeLlm(model="fake", turns=[json_turn(plan_json)])
        result = O.run_orchestrator("X", project_id="demo-project", model=fake_model)
        json.dumps(result)  # must not raise

    def test_rerun_avoids_colliding_with_existing_feature_ids(self, fake_hub):
        # Simulate a feature already on disk from a prior run.
        (fake_hub["features_dir"] / "F01-existing.md").write_text(
            "# F01: Existing\n\n## Goal\nAlready here.\n\n## Status\nplanning\n", encoding="utf-8",
        )
        plan_json = {
            "goal": "X", "summary": "Y",
            "features": [
                {  # the model re-proposes "F01" — must not collide with the real F01
                    "id": "F01", "title": "New One", "goal": "g1",
                    "acceptance_criteria": ["c1"], "files_likely_touched": [], "dependencies": [], "assigned_lead": "feature-lead",
                },
                {  # depends on the model's own "F01" — that reference must be remapped too
                    "id": "F02", "title": "New Two", "goal": "g2",
                    "acceptance_criteria": ["c2"], "files_likely_touched": [], "dependencies": ["F01"], "assigned_lead": "feature-lead",
                },
            ],
        }
        fake_model = FakeLlm(model="fake", turns=[json_turn(plan_json)])

        result = O.run_orchestrator("X", project_id="demo-project", model=fake_model)
        assert result["ok"] is True
        assert result["feature_ids"] == ["F02", "F03"]  # F01 already taken, so numbering continues from F02

        existing_still_there = S.load_spec("specs/features/F01-existing.md")
        assert existing_still_there["ok"] is True
        assert existing_still_there["title"] == "Existing"  # untouched, not overwritten

        new_two = S.load_spec("specs/features/F03-new-two.md")
        assert new_two["ok"] is True
        assert new_two["dependencies"] == ["F02"]  # remapped from the model's stale "F01" reference


# ── Feature Lead ─────────────────────────────────────────────────────────

class TestFeatureLead:
    def test_writes_task_specs_and_board_entries(self, fake_hub):
        (fake_hub["features_dir"] / "F01-api-scaffold.md").write_text(FEATURE_MD, encoding="utf-8")

        task_plan_json = {
            "feature": "F01",
            "tasks": [
                {
                    "id": "T01", "title": "Scaffold FastAPI app", "role": "coder",
                    "goal": "Create the FastAPI app with a /health endpoint",
                    "context_files": ["specs/features/F01-api-scaffold.md"],
                    "instructions": "Create src/app/main.py with a FastAPI() instance and a /health route.",
                    "acceptance_criteria": ["GET /health returns 200 with {'status': 'ok'}"],
                    "definition_of_done": ["src/app/main.py exists"],
                },
                {
                    "id": "T02", "title": "Add health endpoint test", "role": "tester",
                    "goal": "Test the /health endpoint",
                    "context_files": ["src/app/main.py"],
                    "instructions": "Write tests/test_health.py using TestClient.",
                    "acceptance_criteria": ["pytest tests/test_health.py passes"],
                    "definition_of_done": ["tests/test_health.py exists"],
                },
            ],
        }
        fake_model = FakeLlm(model="fake", turns=[json_turn(task_plan_json)])

        result = F.run_feature_lead("specs/features/F01-api-scaffold.md", project_id="demo-project", model=fake_model)

        assert result["ok"] is True
        assert result["feature"] == "F01"
        assert result["task_count"] == 2
        assert result["task_ids"] == ["T01", "T02"]
        assert result["tasks_overflow"] is False
        assert all(u["ok"] for u in result["board_updates"])

        t01_path = fake_hub["tasks_dir"] / "F01" / "T01-scaffold-fastapi-app.md"
        assert t01_path.exists()
        loaded = S.load_spec(str(t01_path))
        assert loaded["ok"] is True
        assert loaded["type"] == "task"
        assert loaded["feature"] == "F01"
        assert loaded["role"] == "coder"

        board = json.loads((fake_hub["root"] / "status" / "board.json").read_text())
        by_id = {t["id"]: t for t in board["tasks"]}
        assert by_id["T01"]["status"] == "pending"
        assert by_id["T01"]["feature"] == "F01"
        assert by_id["T02"]["status"] == "pending"

    def test_missing_feature_spec_returns_error(self, fake_hub):
        result = F.run_feature_lead("specs/features/does-not-exist.md", project_id="demo-project")
        assert result["ok"] is False

    def test_non_feature_spec_rejected(self, fake_hub):
        task_like_md = "# T01: Example Task\n\n## Feature\nF01\n\n## Role\ncoder\n\n## Goal\nx\n"
        (fake_hub["tasks_dir"] / "T01-example.md").write_text(task_like_md, encoding="utf-8")
        result = F.run_feature_lead("specs/tasks/T01-example.md", project_id="demo-project")
        assert result["ok"] is False
        assert "not a feature spec" in result["error"].lower()

    def test_max_tasks_caps_and_flags_overflow(self, fake_hub):
        (fake_hub["features_dir"] / "F01-api-scaffold.md").write_text(FEATURE_MD, encoding="utf-8")
        tasks = [
            {
                "id": f"T0{i}", "title": f"Task {i}", "role": "coder", "goal": f"Goal {i}",
                "context_files": [], "instructions": "Do it.",
                "acceptance_criteria": [f"Criterion {i}"], "definition_of_done": [],
            }
            for i in range(1, 6)
        ]
        fake_model = FakeLlm(model="fake", turns=[json_turn({"feature": "F01", "tasks": tasks})])

        result = F.run_feature_lead(
            "specs/features/F01-api-scaffold.md", project_id="demo-project", model=fake_model, max_tasks=3
        )
        assert result["ok"] is True
        assert result["task_count"] == 3
        assert result["tasks_overflow"] is True

    def test_invalid_structured_output_returns_error_not_exception(self, fake_hub):
        (fake_hub["features_dir"] / "F01-api-scaffold.md").write_text(FEATURE_MD, encoding="utf-8")
        fake_model = FakeLlm(model="fake", turns=[json_turn({"feature": "F01"})])  # missing 'tasks'
        result = F.run_feature_lead("specs/features/F01-api-scaffold.md", project_id="demo-project", model=fake_model)
        assert result["ok"] is False
        assert "schema" in result["error"].lower() or "validation" in result["error"].lower()

    def test_result_is_json_serializable(self, fake_hub):
        (fake_hub["features_dir"] / "F01-api-scaffold.md").write_text(FEATURE_MD, encoding="utf-8")
        fake_model = FakeLlm(model="fake", turns=[json_turn({
            "feature": "F01",
            "tasks": [{
                "id": "T01", "title": "One", "role": "coder", "goal": "g",
                "context_files": [], "instructions": "do it",
                "acceptance_criteria": ["c"], "definition_of_done": [],
            }],
        })])
        result = F.run_feature_lead("specs/features/F01-api-scaffold.md", project_id="demo-project", model=fake_model)
        json.dumps(result)  # must not raise

    def test_rerun_avoids_colliding_with_existing_task_ids(self, fake_hub):
        (fake_hub["features_dir"] / "F01-api-scaffold.md").write_text(FEATURE_MD, encoding="utf-8")
        existing_task_dir = fake_hub["tasks_dir"] / "F01"
        existing_task_dir.mkdir(parents=True)
        (existing_task_dir / "T01-existing.md").write_text(
            "# T01: Existing\n\n## Feature\nF01\n\n## Role\ncoder\n\n## Goal\nAlready here.\n\n"
            "## Acceptance Criteria\n- [ ] x\n\n## Status\npending\n",
            encoding="utf-8",
        )
        fake_model = FakeLlm(model="fake", turns=[json_turn({
            "feature": "F01",
            "tasks": [{  # the model re-proposes "T01" — must not collide with the real T01
                "id": "T01", "title": "New Task", "role": "tester", "goal": "g",
                "context_files": [], "instructions": "do it",
                "acceptance_criteria": ["c"], "definition_of_done": [],
            }],
        })])

        result = F.run_feature_lead("specs/features/F01-api-scaffold.md", project_id="demo-project", model=fake_model)
        assert result["ok"] is True
        assert result["task_ids"] == ["T02"]  # T01 already taken for this feature

        existing_still_there = S.load_spec(str(existing_task_dir / "T01-existing.md"))
        assert existing_still_there["ok"] is True
        assert existing_still_there["title"] == "Existing"  # untouched, not overwritten
