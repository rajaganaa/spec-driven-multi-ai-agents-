"""
hub/agents/specialists/tester.py — Level 2 specialist: Tester

Role  : run tests, read errors, report failures
Tools : read_file, run_terminal, run_tests
Model : gemini-2.5-flash (config/agents.yaml -> specialists.tester.model)
"""

from __future__ import annotations

import asyncio
from typing import Optional, Union

from google.adk.agents import LlmAgent
from google.adk.models.base_llm import BaseLlm

from hub.agents.config import get_specialist_config, resolve_model
from hub.agents.specialists.common import DEFAULT_MAX_TURNS, build_specialist_agent, run_specialist_task

ROLE = "tester"


def _build_instruction() -> str:
    return (
        "You are the Tester specialist in a spec-driven coding hub.\n"
        "Verify the task below by actually running its tests — never by "
        "reading code and guessing whether it would pass.\n\n"
        "Rules:\n"
        "- Prefer run_tests for the suite/path named in the task's "
        "acceptance criteria or definition of done; use run_terminal "
        "only for commands run_tests can't express.\n"
        "- read_file the test output / relevant source if a failure needs "
        "explaining.\n"
        "- You cannot write or edit files — if something needs a code fix, "
        "that's a Coder's job, not yours. Report the failure clearly "
        "instead of attempting to fix it yourself.\n"
        "- Work only from the task spec and context files given below; you "
        "have no prior conversation history.\n"
        "- When you're done, reply with a short text summary: the exact "
        "command(s) you ran, whether they passed or failed, and for any "
        "failure, the specific failing test name(s) and error message(s).\n"
        "- Do not pad your final reply with unrelated commentary."
    )


def build_agent(project_id: str, model: Optional[Union[str, BaseLlm]] = None) -> LlmAgent:
    """Construct the Tester LlmAgent. Exposed standalone so tests can
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


async def run_tester_async(
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


def run_tester(
    task_id: str,
    project_id: Optional[str] = None,
    model: Optional[Union[str, BaseLlm]] = None,
    max_turns: int = DEFAULT_MAX_TURNS,
    extra_context: Optional[str] = None,
) -> dict:
    """Synchronous wrapper around run_tester_async."""
    return asyncio.run(
        run_tester_async(task_id, project_id=project_id, model=model, max_turns=max_turns, extra_context=extra_context)
    )
