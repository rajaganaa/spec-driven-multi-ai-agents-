"""
tests/test_api.py — Part 4: FastAPI wrapper integration test

Exercises POST /api/new -> POST /api/plan -> POST /api/run ->
GET /api/status -> GET /api/files -> GET /api/files/content end to
end through Starlette's TestClient, with the same isolated-filesystem
+ FakeLlm approach tests/test_cli.py's
TestFullPipelineIntegration.test_new_plan_run_status_round_trip uses —
only the model call is faked; everything else (file writes, board.json
updates, git commits) is real.
"""

from __future__ import annotations

import asyncio
import json
import time

import pytest
from fastapi.testclient import TestClient
from google.adk.models.llm_response import LlmResponse
from google.genai import types

import api as api_module
import cli.main as cli_main
import hub.agents.feature_lead as feature_lead_mod
import hub.agents.orchestrator as orchestrator_mod
import hub.runner.task_runner as task_runner_mod
from hub.memory import spec_loader as S
from hub.tools import tools as TOOLS
from tests.fake_llm import FakeLlm, json_turn


def _function_call_turn(name, args):
    return LlmResponse(content=types.Content(role="model", parts=[types.Part.from_function_call(name=name, args=args)]))


def _text_turn(text):
    return LlmResponse(content=types.Content(role="model", parts=[types.Part.from_text(text=text)]))


@pytest.fixture
def isolated_hub(tmp_path, monkeypatch):
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

    monkeypatch.setattr(cli_main, "META_PATH", root / "project.meta.json")
    monkeypatch.setattr(cli_main, "BOARD_PATH", root / "status" / "board.json")

    return {"root": root}


def test_full_cycle_through_api(isolated_hub, monkeypatch):
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
        _function_call_turn("write_file", {"path": "src/app/main.py", "content": "print('hello')\n"}),
        _text_turn("Created src/app/main.py."),
    ])

    real_run_orchestrator_async = orchestrator_mod.run_orchestrator_async
    real_run_feature_lead_async = feature_lead_mod.run_feature_lead_async
    real_run_task_async = task_runner_mod.run_task_async

    # api.py calls orchestrator.run_orchestrator_async / feature_lead.run_feature_lead_async
    # directly (not through cli.main), so patch them on the modules api.py imported.
    monkeypatch.setattr(
        api_module.orchestrator, "run_orchestrator_async",
        lambda goal, project_id=None, model=None, max_features=None:
            real_run_orchestrator_async(goal, project_id=project_id, model=fake_model, max_features=max_features),
    )
    monkeypatch.setattr(
        api_module.feature_lead, "run_feature_lead_async",
        lambda feature_spec_path, project_id=None, model=None, max_tasks=None:
            real_run_feature_lead_async(feature_spec_path, project_id=project_id, model=fake_model, max_tasks=max_tasks),
    )
    monkeypatch.setattr(
        api_module.task_runner, "run_task_async",
        lambda task_id, project_id=None, model=None, max_turns=None, max_retries=None:
            real_run_task_async(task_id, project_id=project_id, model=fake_model, max_turns=max_turns, max_retries=max_retries),
    )

    client = TestClient(api_module.app)

    new_resp = client.post("/api/new", json={"goal": "Build a hello world FastAPI app"})
    assert new_resp.status_code == 200, new_resp.text
    project_id = new_resp.json()["project"]["project_id"]

    plan_resp = client.post("/api/plan", json={})
    assert plan_resp.status_code == 200, plan_resp.text
    plan_body = plan_resp.json()
    assert plan_body["ok"] is True
    assert plan_body["total_tasks"] == 1
    assert plan_body["features"][0]["feature"] == "F01"

    run_resp = client.post("/api/run", json={"task_id": "T01"})
    assert run_resp.status_code == 200, run_resp.text
    assert run_resp.json()["started"] is True

    # /api/run is fire-and-forget (BackgroundTasks) — poll /api/status
    # until the run finishes, same as the React dashboard would.
    deadline = time.monotonic() + 10
    tasks = []
    while time.monotonic() < deadline:
        status_resp = client.get("/api/status")
        assert status_resp.status_code == 200
        body = status_resp.json()
        tasks = body["tasks"]
        if tasks and tasks[0]["status"] in ("done", "failed") and not body["run_state"]["running"]:
            break
        time.sleep(0.2)

    assert tasks, "expected at least one task on the board"
    assert tasks[0]["status"] == "done", tasks

    files_resp = client.get("/api/files")
    assert files_resp.status_code == 200
    file_paths = [f["path"] for f in files_resp.json()["files"]]
    assert "src/app/main.py" in file_paths

    content_resp = client.get("/api/files/content", params={"path": "src/app/main.py"})
    assert content_resp.status_code == 200
    assert content_resp.json()["content"] == "print('hello')\n"

    # Path traversal must be rejected, not silently resolved.
    traversal_resp = client.get("/api/files/content", params={"path": "../../etc/passwd"})
    assert traversal_resp.status_code == 400

    model_status_resp = client.get("/api/model-status")
    assert model_status_resp.status_code == 200
    assert model_status_resp.json()["active_backend"] == "gemini"  # VLLM_BASE_URL unset in test env

    health_resp = client.get("/health")
    assert health_resp.status_code == 200
