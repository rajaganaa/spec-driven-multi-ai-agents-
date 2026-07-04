"""
hub/agents/specialists/coder.py — Level 2 specialist: Coder

Role  : implement the files a task requires
Tools : read_file, write_file, apply_patch, search_code
Model : gemini-2.5-flash (config/agents.yaml -> specialists.coder.model)
"""

from __future__ import annotations

import asyncio
from typing import Optional, Union

from google.adk.agents import LlmAgent
from google.adk.models.base_llm import BaseLlm

from hub.agents.config import get_specialist_config, resolve_model
from hub.agents.specialists.common import DEFAULT_MAX_TURNS, build_specialist_agent, run_specialist_task

ROLE = "coder"


def _build_instruction() -> str:
    return (
        "You are the Coder specialist in a spec-driven coding hub.\n"
        "Implement exactly the task below using read_file / write_file / "
        "apply_patch / search_code.\n\n"
        "Rules:\n"
        "- Prefer apply_patch for small edits to an existing file; use "
        "write_file for new files or full rewrites.\n"
        "- read_file any context file or existing file you need before "
        "writing — don't guess at content you haven't read.\n"
        "- Follow the acceptance criteria exactly; don't add unrequested "
        "scope.\n"
        "- Work only from the task spec and context files given below; you "
        "have no prior conversation history.\n"
        "- When you're done, reply with a short text summary: files created "
        "or modified (with paths), and a one-line confirmation for each "
        "acceptance criterion. If you could not finish, say exactly what's "
        "blocking you.\n"
        "- Do not pad your final reply with unrelated commentary."
    )


def build_agent(project_id: str, model: Optional[Union[str, BaseLlm]] = None) -> LlmAgent:
    """Construct the Coder LlmAgent. Exposed standalone so tests can
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


async def run_coder_async(
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


def run_coder(
    task_id: str,
    project_id: Optional[str] = None,
    model: Optional[Union[str, BaseLlm]] = None,
    max_turns: int = DEFAULT_MAX_TURNS,
    extra_context: Optional[str] = None,
) -> dict:
    """Synchronous wrapper around run_coder_async."""
    return asyncio.run(
        run_coder_async(task_id, project_id=project_id, model=model, max_turns=max_turns, extra_context=extra_context)
    )
