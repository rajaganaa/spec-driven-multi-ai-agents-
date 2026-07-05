"""
hub/agents/specialists/explorer.py — Level 2 specialist: Explorer

Role  : map the repo, find files relevant to a task
Tools : read_file, list_dir, search_code (read-only — no write, no run)
Model : gemini-2.5-flash (config/agents.yaml -> specialists.explorer.model)
"""

from __future__ import annotations

import asyncio
from typing import Optional, Union

from google.adk.agents import LlmAgent
from google.adk.models.base_llm import BaseLlm

from hub.agents.config import get_specialist_config, resolve_model
from hub.agents.specialists.common import DEFAULT_MAX_TURNS, build_specialist_agent, run_specialist_task

ROLE = "explorer"


def _build_instruction() -> str:
    return (
        "You are the Explorer specialist in a spec-driven coding hub.\n"
        "Your only job is reconnaissance: map the relevant parts of the repo "
        "for the task below, using read_file / list_dir / search_code.\n\n"
        "Rules:\n"
        "- You have read-only tools — no write_file, no run_terminal.\n"
        "- Work only from the task spec and context files given below; you "
        "have no prior conversation history.\n"
        "- When you're done, reply with a short text summary: relevant files "
        "found (with paths), what each one contains or is responsible for, "
        "and anything the next agent should know before implementing.\n"
        "- Do not pad your final reply with unrelated commentary."
    )


def build_agent(project_id: str, model: Optional[Union[str, BaseLlm]] = None) -> LlmAgent:
    """Construct the Explorer LlmAgent. Exposed standalone so tests can
    inject a fake model."""
    cfg = get_specialist_config(ROLE)
    return build_specialist_agent(
        role=ROLE,
        project_id=project_id,
        instruction=_build_instruction(),
        allowed_tools=cfg.get("allowed_tools", []),
        model=model or resolve_model(cfg.get("model", "gemini-2.5-flash")),
        description=cfg.get("description"),
    )


async def run_explorer_async(
    task_id: str,
    project_id: Optional[str] = None,
    model: Optional[Union[str, BaseLlm]] = None,
    max_turns: int = DEFAULT_MAX_TURNS,
    extra_context: Optional[str] = None,
    feature: Optional[str] = None,
) -> dict:
    return await run_specialist_task(
        ROLE, build_agent, task_id, project_id=project_id, model=model,
        max_turns=max_turns, extra_context=extra_context, feature=feature,
    )


def run_explorer(
    task_id: str,
    project_id: Optional[str] = None,
    model: Optional[Union[str, BaseLlm]] = None,
    max_turns: int = DEFAULT_MAX_TURNS,
    extra_context: Optional[str] = None,
) -> dict:
    """Synchronous wrapper around run_explorer_async."""
    return asyncio.run(
        run_explorer_async(task_id, project_id=project_id, model=model, max_turns=max_turns, extra_context=extra_context)
    )
