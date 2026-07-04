"""
hub/agents/orchestrator.py — Part D: Orchestrator agent
===========================================================

Input  : a user goal, in plain English
Output : specs/00-project-plan.md + specs/features/F*.md
Model  : gemini-2.5-pro (config/agents.yaml -> orchestrator.model)

WHAT IT DOES
------------
1. Builds an ADK LlmAgent constrained to return a `ProjectPlan`
   (hub/agents/schemas.py) via `output_schema` — structured data, not
   free-form markdown or tool calls. See schemas.py for why.
2. Runs that agent for exactly one turn, with the user's goal (plus a
   little project.meta.json context: stack, constraints) as the only
   input. No prior chat history is used or kept — every call starts a
   fresh InMemorySessionService session, matching the "never holds full
   chat history" design principle.
3. Deterministically renders the returned plan into the exact markdown
   template hub/memory/spec_loader.py expects, and writes it via
   hub.tools.tools.write_spec_file() (sandboxed to specs/ — see that
   module for why specs/ has its own sandbox separate from the
   per-project workspace).

This module has no CLI/runner wiring of its own — `run_orchestrator()`
is the single entry point Part E's task_runner / cli/main.py should call.
"""

from __future__ import annotations

import asyncio
import re
from typing import Optional, Union

from google.adk.agents import LlmAgent
from google.adk.models.base_llm import BaseLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import ValidationError

from hub.agents.config import get_agent_config, resolve_model
from hub.agents.schemas import FeaturePlanItem, ProjectPlan
from hub.memory import spec_loader
from hub.tools import tools

APP_NAME = "my-agent-hub"
ORCHESTRATOR_OUTPUT_KEY = "orchestrator_plan"


# ── Result helpers (same shape as hub/tools/tools.py) ──────────────────────

def _ok(**kwargs) -> dict:
    return {"ok": True, "error": None, **kwargs}


def _err(message: str, **kwargs) -> dict:
    return {"ok": False, "error": message, **kwargs}


# ── Instruction + agent construction ────────────────────────────────────────

def _build_instruction(max_features: int) -> str:
    return (
        "You are the Orchestrator for a spec-driven multi-agent coding hub.\n"
        "You receive a user's goal in plain English and turn it into a project plan.\n\n"
        "Rules:\n"
        f"- Produce between 1 and {max_features} features. Prefer the smallest number "
        f"that cleanly separates concerns; never exceed {max_features}.\n"
        "- Each feature must be small enough that one Feature Lead could own it "
        "end-to-end — it will later be broken into 3-8 implementation tasks.\n"
        "- Write concrete, testable acceptance criteria for every feature "
        "(e.g. 'POST /auth/login returns a JWT', not 'login works').\n"
        "- If one feature depends on another, list the other feature's id in "
        "its dependencies (e.g. an API feature that needs auth first).\n"
        "- Base your plan only on the goal and project context given to you — you "
        "have no tools and no access to prior conversation history.\n"
        "- Return only the structured plan; no extra commentary."
    )


def build_orchestrator_agent(
    model: Optional[Union[str, BaseLlm]] = None,
    max_features: Optional[int] = None,
) -> LlmAgent:
    """Construct the Orchestrator LlmAgent. Exposed standalone (not just
    inside run_orchestrator) so tests can inject a fake model."""
    cfg = get_agent_config("orchestrator")
    resolved_model = model or resolve_model(cfg.get("model", "gemini-2.5-pro"))
    resolved_max_features = max_features or cfg.get("max_features", 7)

    return LlmAgent(
        name="orchestrator",
        model=resolved_model,
        description=cfg.get("description") or "Decomposes a user goal into a project plan and feature specs.",
        instruction=_build_instruction(resolved_max_features),
        output_schema=ProjectPlan,
        output_key=ORCHESTRATOR_OUTPUT_KEY,
        # Structured output mode: no tool calls, no agent transfer.
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
    )


def _build_user_message(goal: str, meta: dict) -> str:
    parts = [f"User goal:\n{goal.strip()}"]
    if meta.get("ok"):
        stack = meta.get("stack") or []
        constraints = meta.get("constraints") or []
        if stack:
            parts.append("Project stack: " + ", ".join(str(s) for s in stack))
        if constraints:
            parts.append("Project constraints: " + "; ".join(str(c) for c in constraints))
    return "\n\n".join(parts)


# ── Markdown rendering (deterministic — see schemas.py design note) ────────

def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return (slug[:40] or "untitled")


def _next_feature_number() -> int:
    """Smallest unused F<NN> number under specs/features/, so re-running
    the Orchestrator (e.g. to add more features later) never collides
    with — and silently overwrites — an existing feature spec. The
    LLM's own proposed ids are not trusted for this; see
    _renumber_features below."""
    features_dir = tools.SPECS_ROOT / "features"
    if not features_dir.exists():
        return 1
    nums = [int(m.group(1)) for p in features_dir.glob("F*.md") if (m := re.match(r"F(\d+)", p.stem))]
    return (max(nums) + 1) if nums else 1


def _renumber_features(features: list) -> list:
    """Reassign every feature's id to a fresh, sequential, non-colliding
    F<NN>, remapping any inter-feature `dependencies` references that
    pointed at the old (LLM-proposed) ids accordingly. References to
    ids outside this batch (e.g. an existing earlier feature) are left
    untouched."""
    start_num = _next_feature_number()
    id_map = {item.id: f"F{start_num + i:02d}" for i, item in enumerate(features)}
    return [
        item.model_copy(update={
            "id": id_map[item.id],
            "dependencies": [id_map.get(d, d) for d in item.dependencies],
        })
        for item in features
    ]


def _render_list(items: list) -> str:
    return "\n".join(f"- {i}" for i in items) if items else "(none)"


def _render_checklist(items: list) -> str:
    return "\n".join(f"- [ ] {c}" for c in items) if items else "- [ ] (none specified)"


def _render_feature_spec_md(item: FeaturePlanItem) -> str:
    return (
        f"# {item.id}: {item.title}\n\n"
        f"## Goal\n{item.goal}\n\n"
        f"## Acceptance Criteria\n{_render_checklist(item.acceptance_criteria)}\n\n"
        f"## Files Likely Touched\n{_render_list(item.files_likely_touched)}\n\n"
        f"## Dependencies\n{_render_list(item.dependencies)}\n\n"
        f"## Assigned Lead\n{item.assigned_lead}\n\n"
        "## Status\nplanning\n"
    )


def _render_project_plan_md(goal: str, summary: str, features: list) -> str:
    feature_lines = "\n".join(f"- {f.id}: {f.title} — assigned to {f.assigned_lead}" for f in features)
    return (
        "# Project Plan\n\n"
        f"## Goal\n{goal}\n\n"
        f"## Summary\n{summary}\n\n"
        f"## Features\n{feature_lines}\n\n"
        "## Status\nplanning\n"
    )


# ── Entry points ─────────────────────────────────────────────────────────

async def run_orchestrator_async(
    goal: str,
    project_id: Optional[str] = None,
    model: Optional[Union[str, BaseLlm]] = None,
    max_features: Optional[int] = None,
) -> dict:
    """Decompose `goal` into a project plan + feature specs, writing
    specs/00-project-plan.md and specs/features/F*.md. Each call is a
    fresh, single-turn session — no chat history is used or kept."""
    if not goal or not goal.strip():
        return _err("goal must not be empty")

    resolved_project_id = project_id or spec_loader.get_active_project_id()
    if not resolved_project_id:
        return _err("No project_id given and none found in project.meta.json")

    cfg = get_agent_config("orchestrator")
    resolved_max_features = max_features or cfg.get("max_features", 7)

    meta = spec_loader.load_project_meta()
    agent = build_orchestrator_agent(model=model, max_features=resolved_max_features)
    user_message = _build_user_message(goal, meta)

    session_service = InMemorySessionService()
    session = await session_service.create_session(app_name=APP_NAME, user_id=resolved_project_id)
    runner = Runner(agent=agent, app_name=APP_NAME, session_service=session_service)

    try:
        async for _event in runner.run_async(
            user_id=resolved_project_id,
            session_id=session.id,
            new_message=types.Content(role="user", parts=[types.Part.from_text(text=user_message)]),
        ):
            pass
    except ValidationError as e:
        return _err(f"Orchestrator output failed schema validation: {e}")
    except Exception as e:  # ADK / model-call failure — report, don't crash the caller
        return _err(f"Orchestrator run failed: {e}")

    session = await session_service.get_session(
        app_name=APP_NAME, user_id=resolved_project_id, session_id=session.id
    )
    raw_plan = session.state.get(ORCHESTRATOR_OUTPUT_KEY) if session else None
    if not raw_plan:
        return _err("Orchestrator produced no structured plan output")

    try:
        plan = ProjectPlan.model_validate(raw_plan)
    except ValidationError as e:
        return _err(f"Orchestrator output failed schema validation: {e}")

    overflow = len(plan.features) > resolved_max_features
    features = _renumber_features(plan.features[:resolved_max_features])

    plan_write = tools.write_spec_file(
        "specs/00-project-plan.md", _render_project_plan_md(plan.goal or goal, plan.summary, features)
    )
    if not plan_write.get("ok"):
        return plan_write

    feature_spec_paths = []
    for item in features:
        rel_path = f"specs/features/{item.id}-{_slugify(item.title)}.md"
        write_result = tools.write_spec_file(rel_path, _render_feature_spec_md(item))
        if not write_result.get("ok"):
            return write_result
        feature_spec_paths.append(rel_path)

    return _ok(
        project_id=resolved_project_id,
        goal=goal,
        project_plan_path="specs/00-project-plan.md",
        feature_spec_paths=feature_spec_paths,
        feature_ids=[f.id for f in features],
        feature_count=len(features),
        features_overflow=overflow,
        summary=plan.summary,
    )


def run_orchestrator(
    goal: str,
    project_id: Optional[str] = None,
    model: Optional[Union[str, BaseLlm]] = None,
    max_features: Optional[int] = None,
) -> dict:
    """Synchronous wrapper around run_orchestrator_async — the entry
    point for cli/main.py (`agent new <goal>`)."""
    return asyncio.run(
        run_orchestrator_async(goal, project_id=project_id, model=model, max_features=max_features)
    )
