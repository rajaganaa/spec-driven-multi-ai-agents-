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

from hub.agents.config import get_rag_config
from hub.memory import spec_loader, vector_store
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


# ── RAG retrieval (Phase 2) ──────────────────────────────────────────────

def _retrieval_query_text(context: dict) -> str:
    """The current task's title/description, used as the retrieval
    query — falls back to the start of the assembled prompt if a task
    spec is missing a title/goal for some reason."""
    task_spec = context.get("task_spec") or {}
    parts = [task_spec.get("title"), task_spec.get("goal")]
    query = " ".join(p for p in parts if p)
    return query or (context.get("prompt") or "")[:500]


def _build_retrieval_note(project_id: str, context: dict) -> Optional[str]:
    """Fetch relevant past work (completed specs, code diffs, Reviewer/
    Tester feedback — see hub/memory/vector_store.py) for this project
    and format it as a prompt section. Returns None if RAG is disabled
    (config/agents.yaml's rag.enabled), retrieval fails, or there's
    nothing relevant yet — callers should treat None as "nothing to
    add", never as an error that should block the task."""
    rag_cfg = get_rag_config()
    if not rag_cfg.get("enabled", True):
        return None

    query_text = _retrieval_query_text(context)
    if not query_text.strip():
        return None

    retrieval = vector_store.retrieve_relevant(project_id, query_text, top_k=rag_cfg.get("top_k", 5))
    if not retrieval.get("ok") or not retrieval.get("matches"):
        return None

    lines = ["## Relevant Past Work", "(Retrieved from this project's history — may or may not be applicable.)"]
    for match in retrieval["matches"]:
        meta = match.get("metadata") or {}
        label = meta.get("kind") or "memory"
        task_ref = f" ({meta['task_id']})" if meta.get("task_id") else ""
        lines.append(f"### {label}{task_ref}\n{match.get('text', '')}")
    return "\n\n".join(lines)


# ── Shared entry point used by explorer/coder/tester/reviewer ──────────────

async def run_specialist_task(
    role: str,
    build_agent_fn: Callable[..., LlmAgent],
    task_id: str,
    project_id: Optional[str] = None,
    model: Optional[Union[str, BaseLlm]] = None,
    max_turns: int = DEFAULT_MAX_TURNS,
    extra_context: Optional[str] = None,
    feature: Optional[str] = None,
) -> dict:
    """Load task_id's entire context (hub.memory.spec_loader.build_agent_context
    — spec + listed files, nothing else, no chat history), run the
    specialist's agent loop on it, and tag the result with
    task_id/feature/role/project_id for task_runner.py.

    `extra_context`, if given, is appended to the prompt — used by
    task_runner.py on retries to tell the specialist what went wrong
    last time, so a retry can actually fix something rather than
    blindly repeating the same failing actions."""
    context = spec_loader.build_agent_context(task_id, feature=feature)
    if not context.get("ok"):
        return context

    resolved_project_id = project_id or context.get("project_id") or spec_loader.get_active_project_id()
    if not resolved_project_id:
        return _err("No project_id given and none found in project.meta.json")

    agent = build_agent_fn(resolved_project_id, model=model)

    retrieval_note = _build_retrieval_note(resolved_project_id, context)
    if retrieval_note:
        extra_context = f"{extra_context}\n\n{retrieval_note}" if extra_context else retrieval_note

    prompt_text = context["prompt"]
    if extra_context:
        prompt_text = f"{prompt_text}\n\n## Additional Context\n{extra_context}"

    run_result = await run_agent_loop(agent, resolved_project_id, prompt_text, max_turns=max_turns)

    return {
        **run_result,
        "task_id": context.get("task_id", task_id),
        "feature": context.get("feature"),
        "role": role,
        "project_id": resolved_project_id,
    }
