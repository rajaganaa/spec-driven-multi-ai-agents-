"""
hub/agents/specialists/common.py — shared machinery for Level 2 specialists
(Explorer, Coder, Tester, Reviewer).

Specialists are different from Orchestrator/Feature Lead (Part D): those
two use ADK's `output_schema` for single-turn structured output with no
tools. Specialists do the opposite — they're real multi-turn
tool-calling agents (the actual "Tools do real work" loop), so this
module:

  1. Resolves a role's `allowed_tools` (from config/agents.yaml) into
     FunctionTool-wrapped hub.tools.tools.ProjectTools methods, bound to
     one project — see build_tools().
  2. Drives one ADK agent through its full tool-calling loop for a
     single task to completion (or until it hits max_llm_calls), and
     extracts a clean tool-call log from the raw event stream — see
     run_agent_loop().
  3. Wraps "load this task's context, build the agent, run the loop" as
     one shared entry point — see run_specialist_task() — so
     explorer.py / coder.py / tester.py / reviewer.py only need to
     define their own instruction text and tool set.

hub/runner/task_runner.py (Part E) is the only thing that should call
run_specialist_task() (via each role module's run_<role>_async/run_<role>).
"""

from __future__ import annotations

from typing import Callable, Optional, Union

from google.adk.agents import LlmAgent
from google.adk.agents.invocation_context import LlmCallsLimitExceededError
from google.adk.agents.run_config import RunConfig
from google.adk.models.base_llm import BaseLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import FunctionTool
from google.genai import types

from hub.memory import spec_loader
from hub.tools.tools import ProjectTools

APP_NAME = "my-agent-hub"
DEFAULT_MAX_TURNS = 12

# Name -> ProjectTools method name. A dict (not direct introspection) so a
# typo in config/agents.yaml's allowed_tools degrades to "tool skipped",
# never to "arbitrary ProjectTools method exposed".
_TOOL_METHOD_NAMES = {
    "read_file": "read_file",
    "write_file": "write_file",
    "apply_patch": "apply_patch",
    "list_dir": "list_dir",
    "search_code": "search_code",
    "run_terminal": "run_terminal",
    "run_tests": "run_tests",
    "git_status": "git_status",
    "git_commit": "git_commit",
}


# ── Result helpers (same shape as hub/tools/tools.py) ──────────────────────

def _ok(**kwargs) -> dict:
    return {"ok": True, "error": None, **kwargs}


def _err(message: str, **kwargs) -> dict:
    return {"ok": False, "error": message, **kwargs}


# ── Tool resolution ─────────────────────────────────────────────────────

def build_tools(project_id: str, allowed_tools: list) -> list:
    """Resolve tool names (config/agents.yaml's allowed_tools) into
    FunctionTool-wrapped ProjectTools methods bound to one project.
    Unknown names are skipped, not raised — a config typo should mean
    "this tool isn't available", not "agent construction crashes"."""
    bound = ProjectTools(project_id)
    resolved = []
    for name in allowed_tools or []:
        method_name = _TOOL_METHOD_NAMES.get(name)
        if method_name and hasattr(bound, method_name):
            resolved.append(FunctionTool(getattr(bound, method_name)))
    return resolved


def build_specialist_agent(
    role: str,
    project_id: str,
    instruction: str,
    allowed_tools: list,
    model: Optional[Union[str, BaseLlm]] = None,
    description: Optional[str] = None,
) -> LlmAgent:
    """Construct one specialist's LlmAgent: real tools, multi-turn
    tool-calling (no output_schema — that's only for Part D's planners)."""
    return LlmAgent(
        name=role,
        model=model or "gemini-2.5-flash",
        description=description or f"{role} specialist",
        instruction=instruction,
        tools=build_tools(project_id, allowed_tools),
    )


# ── Run loop ─────────────────────────────────────────────────────────────

async def run_agent_loop(
    agent: LlmAgent,
    project_id: str,
    prompt_text: str,
    max_turns: int = DEFAULT_MAX_TURNS,
) -> dict:
    """Drive one ADK agent through its full tool-calling loop for a
    single task from a fresh session (no chat history) — ADK's Runner
    automatically feeds tool results back to the model and keeps going
    until it stops requesting tools. Returns:

        {"ok": bool, "error": ..., "tool_calls": [{"name","args","result"}],
         "final_text": str|None}

    tool_calls preserves call order — task_runner.py uses it both to
    decide success/failure (did any tool report ok=False or
    passed=False?) and to persist a log for that attempt."""
    session_service = InMemorySessionService()
    session = await session_service.create_session(app_name=APP_NAME, user_id=project_id)
    runner = Runner(agent=agent, app_name=APP_NAME, session_service=session_service)

    tool_calls: list = []
    final_text_parts: list = []
    pending_call: Optional[dict] = None  # most recently requested function_call, awaiting its response

    try:
        async for event in runner.run_async(
            user_id=project_id,
            session_id=session.id,
            new_message=types.Content(role="user", parts=[types.Part.from_text(text=prompt_text)]),
            run_config=RunConfig(max_llm_calls=max_turns),
        ):
            for part in (event.content.parts if event.content else []):
                if part.function_call:
                    pending_call = {"name": part.function_call.name, "args": dict(part.function_call.args or {})}
                elif part.function_response:
                    name = part.function_response.name
                    args = pending_call["args"] if pending_call and pending_call["name"] == name else None
                    tool_calls.append({"name": name, "args": args, "result": part.function_response.response})
                    pending_call = None
                elif part.text:
                    final_text_parts.append(part.text)
    except LlmCallsLimitExceededError:
        return _err(
            f"Specialist exceeded its turn limit ({max_turns} model calls) without finishing",
            tool_calls=tool_calls,
            final_text="\n".join(final_text_parts) or None,
        )
    except Exception as e:  # ADK / model-call failure — report, don't crash the caller
        return _err(
            f"Specialist run failed: {e}",
            tool_calls=tool_calls,
            final_text="\n".join(final_text_parts) or None,
        )

    return _ok(tool_calls=tool_calls, final_text="\n".join(final_text_parts) or None)


# ── Shared entry point used by explorer/coder/tester/reviewer ──────────────

async def run_specialist_task(
    role: str,
    build_agent_fn: Callable[..., LlmAgent],
    task_id: str,
    project_id: Optional[str] = None,
    model: Optional[Union[str, BaseLlm]] = None,
    max_turns: int = DEFAULT_MAX_TURNS,
    extra_context: Optional[str] = None,
) -> dict:
    """Load task_id's entire context (hub.memory.spec_loader.build_agent_context
    — spec + listed files, nothing else, no chat history), run the
    specialist's agent loop on it, and tag the result with
    task_id/feature/role/project_id for task_runner.py.

    `extra_context`, if given, is appended to the prompt — used by
    task_runner.py on retries to tell the specialist what went wrong
    last time, so a retry can actually fix something rather than
    blindly repeating the same failing actions."""
    context = spec_loader.build_agent_context(task_id)
    if not context.get("ok"):
        return context

    resolved_project_id = project_id or context.get("project_id") or spec_loader.get_active_project_id()
    if not resolved_project_id:
        return _err("No project_id given and none found in project.meta.json")

    agent = build_agent_fn(resolved_project_id, model=model)

    prompt_text = context["prompt"]
    if extra_context:
        prompt_text = f"{prompt_text}\n\n## Retry Note\n{extra_context}"

    run_result = await run_agent_loop(agent, resolved_project_id, prompt_text, max_turns=max_turns)

    return {
        **run_result,
        "task_id": context.get("task_id", task_id),
        "feature": context.get("feature"),
        "role": role,
        "project_id": resolved_project_id,
    }
