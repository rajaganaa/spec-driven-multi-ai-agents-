"""
api.py — Part 4: FastAPI wrapper around my-agent-hub

Thin REST layer over the same entry points cli/main.py already uses
(hub.agents.orchestrator, hub.agents.feature_lead, hub.runner.task_runner,
hub.memory.spec_loader). No hub internals are reimplemented here — this
module only adapts their existing {"ok": bool, "error": ...} contract
into HTTP responses.

Run locally:
    uvicorn api:app --reload --port 8080

Endpoints:
    POST /api/new          { goal, stack?, constraints? }      -> create project.meta.json
    POST /api/plan         { model? }                          -> Orchestrator + Feature Leads
    POST /api/run          { task_id?, model?, max_retries? }  -> kicks off task(s) IN THE BACKGROUND
    GET  /api/status                                           -> project meta + board + run state
    GET  /api/files                                            -> list generated files for the active project
    GET  /api/files/content?path=...                           -> read one generated file's content
    GET  /api/model-status                                     -> which backend (vLLM/Gemini) is actually live
    GET  /health                                                -> liveness probe for Cloud Run

IMPORTANT — statelessness note (see DEPLOYMENT.md):
This hub keeps all state on the local filesystem (project.meta.json,
status/board.json, specs/, workspace/projects/<id>/) and one run-state
flag in this process's memory. That's fine on a single long-running
box, but it does NOT survive Cloud Run scaling to >1 instance or an
instance being recycled. See DEPLOYMENT.md for how this is constrained
(min/max instances = 1) and the GCS-backed alternative for real
multi-instance production use.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import List, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from cli.main import create_project_meta  # noqa: E402
from hub.agents import config as agent_config  # noqa: E402
from hub.agents import feature_lead, orchestrator  # noqa: E402
from hub.memory import spec_loader  # noqa: E402
from hub.runner import task_runner  # noqa: E402
from hub.tools import tools as hub_tools  # noqa: E402

# ── App setup ────────────────────────────────────────────────────────────

app = FastAPI(title="AgentForge API", version="2.0")

# CORS: comma-separated list of allowed origins, e.g.
#   FRONTEND_ORIGIN=https://yourname.github.io
# Defaults to "*" for local development ONLY — set FRONTEND_ORIGIN in
# production. allow_credentials must stay False while using "*".
_frontend_origins_env = os.getenv("FRONTEND_ORIGIN", "").strip()
if _frontend_origins_env:
    _allow_origins = [o.strip() for o in _frontend_origins_env.split(",") if o.strip()]
    _allow_credentials = True
else:
    print("[api] WARNING: FRONTEND_ORIGIN not set — defaulting CORS to '*'. "
          "Set FRONTEND_ORIGIN in production (see .env.example).")
    _allow_origins = ["*"]
    _allow_credentials = False

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-process run-state — see the statelessness note in the module
# docstring. Good enough for "is a run currently in flight", not a
# substitute for status/board.json as the source of truth.
_run_state = {"running": False, "kind": None, "last_result": None}


# ── Request models ──────────────────────────────────────────────────────

class NewProjectRequest(BaseModel):
    goal: str = Field(..., min_length=1)
    stack: List[str] = Field(default_factory=lambda: ["python", "fastapi"])
    constraints: List[str] = Field(default_factory=list)


class PlanRequest(BaseModel):
    model: Optional[str] = None


class RunRequest(BaseModel):
    task_id: Optional[str] = None
    model: Optional[str] = None
    max_retries: Optional[int] = None


# ── Helpers ──────────────────────────────────────────────────────────────

def _require_active_project() -> dict:
    """Load project.meta.json or raise a 400 — every endpoint except
    /api/new needs a project to already exist."""
    meta = spec_loader.load_project_meta()
    if not meta.get("ok"):
        raise HTTPException(status_code=400, detail=meta.get("error") or "No active project. Call POST /api/new first.")
    return meta


async def _background_run_task(task_id: str, project_id: str, model: Optional[str], max_retries: Optional[int]) -> None:
    _run_state.update(running=True, kind=f"task:{task_id}", last_result=None)
    try:
        result = await task_runner.run_task_async(
            task_id, project_id=project_id, model=model, max_retries=max_retries
        )
        _run_state["last_result"] = result
    finally:
        _run_state["running"] = False


async def _background_run_pending(project_id: str, model: Optional[str], max_retries: Optional[int]) -> None:
    _run_state.update(running=True, kind="pending", last_result=None)
    try:
        result = await task_runner.run_pending_tasks_async(
            project_id=project_id, model=model, max_retries=max_retries
        )
        _run_state["last_result"] = result
    finally:
        _run_state["running"] = False


# ── Endpoints ────────────────────────────────────────────────────────────

@app.post("/api/new")
async def new_project(req: NewProjectRequest):
    """Create project.meta.json + status/board.json. No LLM call —
    instant, same as `python cli/main.py new`."""
    meta = create_project_meta(goal=req.goal, stack=req.stack, constraints=req.constraints)
    return {"ok": True, "project": meta}


@app.post("/api/plan")
async def plan_project(req: PlanRequest):
    """Run the Orchestrator, then a Feature Lead per feature. Awaited
    inline within this request (not backgrounded like /api/run):
    planning is one or two LLM calls per feature, not a long
    tool-calling loop, so it comfortably finishes within a normal
    request lifetime."""
    meta = _require_active_project()
    project_id = meta["project_id"]

    orch_result = await orchestrator.run_orchestrator_async(meta["goal"], project_id=project_id, model=req.model)
    if not orch_result.get("ok"):
        raise HTTPException(status_code=502, detail=f"Orchestrator failed: {orch_result.get('error')}")

    features = []
    any_failed = False
    total_tasks = 0
    for feature_id, feature_path in zip(orch_result["feature_ids"], orch_result["feature_spec_paths"]):
        fl_result = await feature_lead.run_feature_lead_async(feature_path, project_id=project_id, model=req.model)
        if not fl_result.get("ok"):
            features.append({"feature": feature_id, "ok": False, "error": fl_result.get("error")})
            any_failed = True
            continue
        total_tasks += fl_result["task_count"]
        features.append({
            "feature": feature_id,
            "ok": True,
            "task_count": fl_result["task_count"],
            "task_ids": fl_result["task_ids"],
            "tasks_overflow": fl_result.get("tasks_overflow", False),
        })

    return {
        "ok": not any_failed,
        "feature_count": orch_result["feature_count"],
        "features_overflow": orch_result.get("features_overflow", False),
        "features": features,
        "total_tasks": total_tasks,
    }


@app.post("/api/run")
async def run_tasks(req: RunRequest, background_tasks: BackgroundTasks):
    """Kick off one task or all pending tasks IN THE BACKGROUND and
    return immediately — a full run can take minutes (each specialist's
    tool-calling loop, plus a deliberate 30s pause between tasks to stay
    under upstream rate limits), which is too long for a single HTTP
    request/proxy timeout. Poll GET /api/status to watch it progress."""
    meta = _require_active_project()
    project_id = meta["project_id"]

    if _run_state["running"]:
        raise HTTPException(status_code=409, detail=f"A run is already in progress ({_run_state['kind']}).")

    if req.task_id:
        background_tasks.add_task(_background_run_task, req.task_id, project_id, req.model, req.max_retries)
        return {"ok": True, "started": True, "task_id": req.task_id}

    pending = spec_loader.list_tasks(status="pending")
    if not pending:
        return {"ok": True, "started": False, "message": "Nothing pending. Call /api/plan first."}

    background_tasks.add_task(_background_run_pending, project_id, req.model, req.max_retries)
    return {"ok": True, "started": True, "pending_count": len(pending)}


@app.get("/api/status")
async def get_status():
    meta = spec_loader.load_project_meta()
    tasks = spec_loader.list_tasks()
    return {
        "project": meta if meta.get("ok") else None,
        "tasks": tasks,
        "run_state": _run_state,
    }


@app.get("/api/files")
async def get_files():
    meta = _require_active_project()
    proj_dir = (hub_tools.WORKSPACE_ROOT / meta["project_id"]).resolve()
    if proj_dir != hub_tools.WORKSPACE_ROOT and hub_tools.WORKSPACE_ROOT not in proj_dir.parents:
        raise HTTPException(status_code=400, detail="Invalid project_id")
    if not proj_dir.exists():
        return {"files": []}
    files = [
        # Use as_posix() (not str()) so paths are always "src/app/main.py",
        # never "src\\app\\main.py" on Windows. Clients (and tests) can then
        # rely on a single, platform-independent path format.
        {"name": p.name, "path": p.relative_to(proj_dir).as_posix(), "size": p.stat().st_size}
        for p in proj_dir.rglob("*")
        if p.is_file() and ".git" not in p.parts
    ]
    return {"files": files}


@app.get("/api/files/content")
async def get_file_content(path: str = Query(..., description="Relative path, as returned by /api/files")):
    meta = _require_active_project()
    proj_dir = (hub_tools.WORKSPACE_ROOT / meta["project_id"]).resolve()
    target = (proj_dir / path).resolve()
    # Path-traversal guard: refuse anything that resolves outside the
    # project's own workspace directory (e.g. "../../etc/passwd"),
    # mirroring hub/tools/tools.py's own _safe_path sandboxing.
    if proj_dir not in target.parents and target != proj_dir:
        raise HTTPException(status_code=400, detail="Invalid path")
    if not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    try:
        content = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=415, detail="File is not text (binary content can't be previewed)")
    return {"path": path, "content": content}


@app.get("/api/model-status")
async def model_status():
    """Which backend is actually serving requests right now — vLLM (if
    VLLM_BASE_URL is configured and healthy) or the Gemini fallback."""
    return agent_config.get_model_router_status()


@app.get("/health")
async def health():
    return {"status": "ok"}
