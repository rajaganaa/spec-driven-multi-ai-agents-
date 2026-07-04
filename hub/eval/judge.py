"""
hub/eval/judge.py — LLM-as-judge scorer for hub/eval/runner.py

Same construction pattern as hub/agents/orchestrator.py: an ADK LlmAgent
constrained to return JudgeVerdict (hub/eval/schemas.py) via
output_schema, run for exactly one turn with no chat history, no tools.
The judge only ever sees text (the golden task's spec + rubric, and a
rendering of what the specialist actually did) — it never runs code or
touches the project sandbox itself, so it can't be fooled by anything
outside what's explicitly shown to it, and it can't accidentally mutate
project state.
"""

from __future__ import annotations

import asyncio
from typing import Optional, Union

from google.adk.agents import LlmAgent
from google.adk.models.base_llm import BaseLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import ValidationError

from hub.agents.config import get_agent_config, resolve_model
from hub.eval.golden_tasks import GoldenTask
from hub.eval.schemas import JudgeVerdict

APP_NAME = "my-agent-hub-eval"
JUDGE_OUTPUT_KEY = "judge_verdict"


def _ok(**kwargs) -> dict:
    return {"ok": True, "error": None, **kwargs}


def _err(message: str, **kwargs) -> dict:
    return {"ok": False, "error": message, **kwargs}


def _build_instruction() -> str:
    return (
        "You are an expert code reviewer acting as an impartial judge. You will be shown a "
        "task specification (goal, instructions, acceptance criteria, and optional quality "
        "rubric items) and a record of what an AI coding agent actually produced for that task. "
        "Score every acceptance criterion and every rubric item individually as passed or "
        "failed, with a one-sentence comment each. Then give an overall_score from 0.0 to 1.0 "
        "reflecting holistic quality (this is independent of, and can differ from, the "
        "pass/fail breakdown — e.g. a technically-passing but sloppy solution might still score "
        "0.6). Be strict and specific: if the agent's output doesn't clearly demonstrate a "
        "criterion is met (e.g. no code was actually written, or a test wasn't actually added), "
        "mark it failed rather than assuming good faith. If the task record shows the agent's "
        "run failed or produced no commit, every acceptance criterion should almost always be "
        "scored failed."
    )


def build_judge_agent(model: Optional[Union[str, BaseLlm]] = None) -> LlmAgent:
    """Construct the judge LlmAgent. Exposed standalone (not just inside
    run_judge_async) so tests can inject a fake model, matching
    hub/agents/orchestrator.py's build_orchestrator_agent pattern."""
    cfg = get_agent_config("eval_judge")
    resolved_model = model or resolve_model(cfg.get("model", "gemini-2.5-pro"))

    return LlmAgent(
        name="eval_judge",
        model=resolved_model,
        description=cfg.get("description") or "Scores a completed golden-eval task against its spec and rubric.",
        instruction=_build_instruction(),
        output_schema=JudgeVerdict,
        output_key=JUDGE_OUTPUT_KEY,
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
    )


def _render_criteria(items: list, label: str) -> str:
    if not items:
        return f"{label}: (none)"
    bullets = "\n".join(f"  - {c}" for c in items)
    return f"{label}:\n{bullets}"


def _render_task_output(task_result: dict) -> str:
    """Turn a hub/runner/task_runner.py run_task_async() result into
    plain text the judge can read. Deliberately does not include raw
    tool_calls JSON (noisy, low-signal for grading) — prefers the
    specialist's own final_text summary and, when available, the actual
    code diff (git show) already computed by the caller and passed in
    via task_result['diff_text'], since that's what the criteria are
    really about."""
    if not task_result.get("ok"):
        lines = [
            f"Task run FAILED after {task_result.get('attempt_count', '?')} attempt(s).",
            f"Failure reason: {task_result.get('error')}",
        ]
    else:
        lines = [
            f"Task run SUCCEEDED in {task_result.get('attempt_count', 1)} attempt(s).",
            f"Commit: {task_result.get('commit_sha') or '(nothing to commit)'}",
        ]

    final_text = task_result.get("final_text")
    if final_text:
        lines.append(f"\nSpecialist's final summary:\n{final_text}")

    diff_text = task_result.get("diff_text")
    if diff_text:
        # Keep this bounded — a judge prompt doesn't need an unbounded diff,
        # and this also protects against accidentally blowing the context
        # window on a pathological run.
        lines.append(f"\nCode diff (truncated to 4000 chars):\n{diff_text[:4000]}")

    return "\n".join(lines)


def _build_user_message(task: GoldenTask, task_result: dict) -> str:
    parts = [
        f"# Golden task: {task.id} — {task.title}",
        f"\n## Goal\n{task.goal}",
        f"\n## Instructions given to the agent\n{task.instructions}",
        f"\n## {_render_criteria(task.acceptance_criteria, 'Acceptance criteria (score each — these gate pass/fail)')}",
        f"\n## {_render_criteria(task.rubric, 'Rubric (score each — these do not gate pass/fail, quality only)')}",
        f"\n## What the agent actually did\n{_render_task_output(task_result)}",
    ]
    return "\n".join(parts)


async def run_judge_async(
    task: GoldenTask,
    task_result: dict,
    model: Optional[Union[str, BaseLlm]] = None,
) -> dict:
    """Score one golden task's run result. Never raises — schema/model
    failures come back as {"ok": False, "error": ...}, same contract as
    every other entry point in this hub."""
    agent = build_judge_agent(model=model)
    user_message = _build_user_message(task, task_result)

    session_service = InMemorySessionService()
    session = await session_service.create_session(app_name=APP_NAME, user_id=task.id)
    runner = Runner(agent=agent, app_name=APP_NAME, session_service=session_service)

    try:
        async for _event in runner.run_async(
            user_id=task.id,
            session_id=session.id,
            new_message=types.Content(role="user", parts=[types.Part.from_text(text=user_message)]),
        ):
            pass
    except ValidationError as e:
        return _err(f"Judge output failed schema validation: {e}", task_id=task.id)
    except Exception as e:  # ADK / model-call failure — report, don't crash the caller
        return _err(f"Judge run failed: {e}", task_id=task.id)

    session = await session_service.get_session(app_name=APP_NAME, user_id=task.id, session_id=session.id)
    raw_verdict = session.state.get(JUDGE_OUTPUT_KEY) if session else None
    if not raw_verdict:
        return _err("Judge produced no structured verdict output", task_id=task.id)

    try:
        verdict = JudgeVerdict.model_validate(raw_verdict)
    except ValidationError as e:
        return _err(f"Judge output failed schema validation: {e}", task_id=task.id)

    acceptance_set = set(task.acceptance_criteria)
    acceptance_scores = [c for c in verdict.criterion_scores if c.criterion in acceptance_set]
    # If the judge didn't score every acceptance criterion by exact text
    # match, treat that as incomplete grading rather than silently
    # passing on partial data.
    passed = bool(acceptance_scores) and len(acceptance_scores) == len(task.acceptance_criteria) and all(
        c.passed for c in acceptance_scores
    )

    return _ok(
        task_id=task.id,
        passed=passed,
        overall_score=verdict.overall_score,
        summary=verdict.summary,
        criterion_scores=[c.model_dump() for c in verdict.criterion_scores],
    )


def run_judge(task: GoldenTask, task_result: dict, model: Optional[Union[str, BaseLlm]] = None) -> dict:
    """Synchronous wrapper around run_judge_async."""
    return asyncio.run(run_judge_async(task, task_result, model=model))
