"""
hub/agents/feature_lead.py — Part D: Feature Lead agent
===========================================================

Input  : one feature spec path (e.g. 'specs/features/F01-auth.md')
Output : task specs under specs/tasks/<feature>/T*.md
Model  : gemini-2.5-pro (config/agents.yaml -> feature_lead.model)

WHAT IT DOES
------------
1. Loads the ONE feature spec it owns via hub.memory.spec_loader.load_spec
   and embeds its content directly in the prompt — this is "fresh context
   per worker": the Feature Lead gets exactly its spec, nothing else, no
   prior chat history.
2. Runs an ADK LlmAgent constrained to return a `FeatureTaskPlan`
   (hub/agents/schemas.py) via `output_schema` — see schemas.py for why
   structured output is used instead of a write_file tool.
3. Deterministically renders each task into the exact markdown template
   spec_loader.py expects and writes it via
   hub.tools.tools.write_spec_file(), under the nested
   specs/tasks/<feature>/ layout (see config/agents.yaml).
4. Registers every new task in status/board.json as "pending" via
   hub.memory.spec_loader.update_board_status(), so Part E's task runner
   has something to pick up immediately.

`run_feature_lead()` is the single entry point Part E's task_runner /
cli/main.py should call (once per feature, after the Orchestrator runs).
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

from hub.agents.config import get_agent_config
from hub.agents.schemas import FeatureTaskPlan, TaskPlanItem
from hub.memory import spec_loader
from hub.tools import tools

APP_NAME = "my-agent-hub"
FEATURE_LEAD_OUTPUT_KEY = "feature_lead_plan"


# ── Result helpers (same shape as hub/tools/tools.py) ──────────────────────

def _ok(**kwargs) -> dict:
    return {"ok": True, "error": None, **kwargs}


def _err(message: str, **kwargs) -> dict:
    return {"ok": False, "error": message, **kwargs}


# ── Instruction + agent construction ────────────────────────────────────────

def _build_instruction(max_tasks: int) -> str:
    return (
        "You are a Feature Lead in a spec-driven multi-agent coding hub.\n"
        "You own exactly one feature end-to-end. You are given that feature's "
        "spec below and must break it into atomic implementation tasks.\n\n"
        "Rules:\n"
        f"- Produce between 1 and {max_tasks} tasks. Prefer the smallest number "
        f"that keeps each task atomic; never exceed {max_tasks}.\n"
        "- Each task's role must be exactly one of: explorer, coder, tester, reviewer.\n"
        "- A typical feature needs at least one coder task and one tester task.\n"
        "- List at most 5 context_files per task — only what a specialist truly "
        "needs to read (e.g. the feature spec itself, plus the 1-4 source files "
        "it will touch). Reuse paths from the feature's 'Files Likely Touched'.\n"
        "- Write concrete, testable acceptance criteria for every task.\n"
        "- Order tasks so dependencies come first (e.g. the data model before "
        "the endpoint that uses it).\n"
        "- Base your plan only on the feature spec given to you — you have no "
        "tools and no access to prior conversation history.\n"
        "- Return only the structured task plan; no extra commentary."
    )


def build_feature_lead_agent(
    model: Optional[Union[str, BaseLlm]] = None,
    max_tasks: Optional[int] = None,
) -> LlmAgent:
    """Construct the Feature Lead LlmAgent. Exposed standalone (not just
    inside run_feature_lead) so tests can inject a fake model."""
    cfg = get_agent_config("feature_lead")
    resolved_model = model or cfg.get("model", "gemini-2.5-pro")
    resolved_max_tasks = max_tasks or cfg.get("max_tasks_per_feature", 8)

    return LlmAgent(
        name="feature_lead",
        model=resolved_model,
        description=cfg.get("description") or "Breaks one feature spec into task specs.",
        instruction=_build_instruction(resolved_max_tasks),
        output_schema=FeatureTaskPlan,
        output_key=FEATURE_LEAD_OUTPUT_KEY,
        # Structured output mode: no tool calls, no agent transfer.
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
    )


def _build_user_message(feature_spec: dict) -> str:
    parts = [f"Feature spec ({feature_spec.get('id')}: {feature_spec.get('title')}):"]
    if feature_spec.get("goal"):
        parts.append(f"Goal: {feature_spec['goal']}")
    criteria = feature_spec.get("acceptance_criteria") or []
    if criteria:
        rendered = "\n".join(f"- {c['text']}" for c in criteria)
        parts.append(f"Acceptance criteria:\n{rendered}")
    files = feature_spec.get("files_likely_touched") or []
    if files:
        parts.append("Files likely touched: " + ", ".join(files))
    deps = feature_spec.get("dependencies") or []
    if deps:
        parts.append("Dependencies: " + ", ".join(deps))
    return "\n\n".join(parts)


# ── Markdown rendering (deterministic — see schemas.py design note) ────────

def _next_task_number(feature_id: str) -> int:
    """Smallest unused T<NN> number under specs/tasks/<feature_id>/, so
    re-running a Feature Lead never collides with — and silently
    overwrites — an existing task spec for this feature."""
    tasks_dir = tools.SPECS_ROOT / "tasks" / feature_id
    if not tasks_dir.exists():
        return 1
    nums = [int(m.group(1)) for p in tasks_dir.glob("T*.md") if (m := re.match(r"T(\d+)", p.stem))]
    return (max(nums) + 1) if nums else 1


def _renumber_tasks(feature_id: str, tasks: list) -> list:
    """Reassign every task's id to a fresh, sequential, non-colliding
    T<NN> within this feature. The LLM's own proposed ids are not
    trusted for this — see _next_task_number above. Tasks don't
    reference each other's ids in this schema, so no remap is needed
    beyond the id field itself."""
    start_num = _next_task_number(feature_id)
    return [item.model_copy(update={"id": f"T{start_num + i:02d}"}) for i, item in enumerate(tasks)]


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return (slug[:40] or "untitled")


def _render_list(items: list) -> str:
    return "\n".join(f"- {i}" for i in items) if items else "(none)"


def _render_checklist(items: list) -> str:
    return "\n".join(f"- [ ] {c}" for c in items) if items else "- [ ] (none specified)"


def _render_task_spec_md(feature_id: str, item: TaskPlanItem) -> str:
    return (
        f"# {item.id}: {item.title}\n\n"
        f"## Feature\n{feature_id}\n\n"
        f"## Role\n{item.role}\n\n"
        f"## Goal\n{item.goal}\n\n"
        f"## Context Files (max 5)\n{_render_list(item.context_files)}\n\n"
        f"## Instructions\n{item.instructions}\n\n"
        f"## Acceptance Criteria\n{_render_checklist(item.acceptance_criteria)}\n\n"
        f"## Definition of Done\n{_render_list(item.definition_of_done)}\n\n"
        "## Status\npending\n"
    )


# ── Entry points ─────────────────────────────────────────────────────────

async def run_feature_lead_async(
    feature_spec_path: str,
    project_id: Optional[str] = None,
    model: Optional[Union[str, BaseLlm]] = None,
    max_tasks: Optional[int] = None,
) -> dict:
    """Break the feature spec at `feature_spec_path` into task specs
    under specs/tasks/<feature>/T*.md, and register each as 'pending'
    on the status board. Fresh, single-turn session — no chat history."""
    spec = spec_loader.load_spec(feature_spec_path)
    if not spec.get("ok"):
        return spec
    if spec.get("type") not in ("feature", "unknown"):
        return _err(
            f"{feature_spec_path} is not a feature spec (type={spec.get('type')})",
            path=feature_spec_path,
        )

    feature_id = spec.get("id")
    if not feature_id:
        return _err(f"Could not determine a feature id from {feature_spec_path}", path=feature_spec_path)

    resolved_project_id = project_id or spec_loader.get_active_project_id()
    if not resolved_project_id:
        return _err("No project_id given and none found in project.meta.json")

    cfg = get_agent_config("feature_lead")
    resolved_max_tasks = max_tasks or cfg.get("max_tasks_per_feature", 8)

    agent = build_feature_lead_agent(model=model, max_tasks=resolved_max_tasks)
    user_message = _build_user_message(spec)

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
        return _err(f"Feature Lead output failed schema validation: {e}")
    except Exception as e:  # ADK / model-call failure — report, don't crash the caller
        return _err(f"Feature Lead run failed: {e}")

    session = await session_service.get_session(
        app_name=APP_NAME, user_id=resolved_project_id, session_id=session.id
    )
    raw_plan = session.state.get(FEATURE_LEAD_OUTPUT_KEY) if session else None
    if not raw_plan:
        return _err("Feature Lead produced no structured task plan output")

    try:
        task_plan = FeatureTaskPlan.model_validate(raw_plan)
    except ValidationError as e:
        return _err(f"Feature Lead output failed schema validation: {e}")

    overflow = len(task_plan.tasks) > resolved_max_tasks
    task_items = _renumber_tasks(feature_id, task_plan.tasks[:resolved_max_tasks])

    task_spec_paths = []
    board_updates = []
    for item in task_items:
        rel_path = f"specs/tasks/{feature_id}/{item.id}-{_slugify(item.title)}.md"
        write_result = tools.write_spec_file(rel_path, _render_task_spec_md(feature_id, item))
        if not write_result.get("ok"):
            return write_result
        task_spec_paths.append(rel_path)

        board_result = spec_loader.update_board_status(item.id, "pending")
        board_updates.append(
            {"task_id": item.id, "ok": board_result.get("ok"), "error": board_result.get("error")}
        )

    return _ok(
        project_id=resolved_project_id,
        feature=feature_id,
        feature_spec_path=feature_spec_path,
        task_spec_paths=task_spec_paths,
        task_ids=[t.id for t in task_items],
        task_count=len(task_items),
        tasks_overflow=overflow,
        board_updates=board_updates,
    )


def run_feature_lead(
    feature_spec_path: str,
    project_id: Optional[str] = None,
    model: Optional[Union[str, BaseLlm]] = None,
    max_tasks: Optional[int] = None,
) -> dict:
    """Synchronous wrapper around run_feature_lead_async — the entry
    point for cli/main.py (`agent plan`)."""
    return asyncio.run(
        run_feature_lead_async(feature_spec_path, project_id=project_id, model=model, max_tasks=max_tasks)
    )
