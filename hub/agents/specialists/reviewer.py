"""
hub/agents/specialists/reviewer.py — Level 2 specialist: Reviewer

Role  : code review + security scan on completed task output
Tools : read_file, search_code (read-only — no write, no run)
Model : gemini-2.5-flash (config/agents.yaml -> specialists.reviewer.model)
"""

from __future__ import annotations

import asyncio
from typing import Optional, Union

from google.adk.agents import LlmAgent
from google.adk.models.base_llm import BaseLlm

from hub.agents.config import get_specialist_config, resolve_model
from hub.agents.specialists.common import DEFAULT_MAX_TURNS, build_specialist_agent, run_specialist_task

ROLE = "reviewer"


def _build_instruction() -> str:
    return (
        "You are the Reviewer specialist in a spec-driven coding hub.\n"
        "Review the work done for the task below against its acceptance "
        "criteria, using read_file / search_code.\n\n"
        "Rules:\n"
        "- You have read-only tools — no write_file, no run_terminal. You "
        "report issues; you don't fix them yourself.\n"
        "- Check each acceptance criterion explicitly — don't just skim "
        "for style.\n"
        "- Look for bugs, missed edge cases, obvious security issues "
        "(e.g. secrets in code, unsafe shell/SQL construction, missing "
        "input validation), and anything that doesn't match the task's "
        "instructions.\n"
        "- Work only from the task spec and context files given below; you "
        "have no prior conversation history.\n"
        "- When you're done, reply with a clear verdict — 'Approved' or "
        "'Changes requested' — followed by a concrete, numbered list of "
        "issues (file + what's wrong), or 'No issues found' if everything "
        "checks out.\n"
        "- Do not pad your final reply with unrelated commentary."
    )


def build_agent(project_id: str, model: Optional[Union[str, BaseLlm]] = None) -> LlmAgent:
    """Construct the Reviewer LlmAgent. Exposed standalone so tests can
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


async def run_reviewer_async(
    task_id: str,
    project_id: Optional[str] = None,
    model: Optional[Union[str, BaseLlm]] = None,
    max_turns: int = DEFAULT_MAX_TURNS,
    extra_context: Optional[str] = None,
) -> dict:
    return await run_specialist_task(
        ROLE, build_agent, task_id, project_id=project_id, model=model,
        max_turns=max_turns, extra_context=extra_context,
    )


def run_reviewer(
    task_id: str,
    project_id: Optional[str] = None,
    model: Optional[Union[str, BaseLlm]] = None,
    max_turns: int = DEFAULT_MAX_TURNS,
    extra_context: Optional[str] = None,
) -> dict:
    """Synchronous wrapper around run_reviewer_async."""
    return asyncio.run(
        run_reviewer_async(task_id, project_id=project_id, model=model, max_turns=max_turns, extra_context=extra_context)
    )
