"""
hub/runner/task_runner.py — Part E: Task Runner
===================================================

Given a task_id:
  1. Look up its spec and read its `role` field.
  2. Dispatch to the matching specialist (hub/agents/specialists/) —
     which itself loads the task's full context via
     hub.memory.spec_loader.build_agent_context() and drives the real
     ADK tool-calling loop.
  3. Decide success/failure from what actually happened (tool-level
     errors, failing tests) — not from the specialist's self-report.
  4. On failure, retry (up to config/agents.yaml's workspace.retry_limit,
     default 3), feeding the previous attempt's failure back into the
     next attempt's prompt so a retry can actually fix something.
  5. Persist a log of every attempt, update status/board.json, and
     git-commit on success (config/agents.yaml's git.auto_commit_on_success).

run_task() / run_pending_tasks() are the entry points cli/main.py's
`agent run` command uses.

WHAT THIS DELIBERATELY DOES NOT DO: the blueprint's execution-loop
sketch describes a Tester's failure spawning a *new* fix task for a
Coder. That's a reasonable future extension, but it's a bigger design
than "retry up to 3 times" — this runner retries the *same* task with
its *own* specialist, which is what was actually asked for here.
"""

from __future__ import annotations

import asyncio
import json
from typing import List, Optional, Tuple, Union

from google.adk.models.base_llm import BaseLlm

from hub.agents.config import get_git_config, get_workspace_config
from hub.agents.specialists import ROLE_RUNNERS_ASYNC
from hub.agents.specialists.common import DEFAULT_MAX_TURNS
from hub.memory import spec_loader
from hub.tools import tools


# ── Result helpers (same shape as hub/tools/tools.py) ──────────────────────

def _ok(**kwargs) -> dict:
    return {"ok": True, "error": None, **kwargs}


def _err(message: str, **kwargs) -> dict:
    return {"ok": False, "error": message, **kwargs}


# ── Success determination ──────────────────────────────────────────────────

def _determine_success(role: str, run_result: dict) -> Tuple[bool, str]:
    """Decide whether an attempt actually succeeded, from what the
    specialist's tools reported — not from its self-described final
    text, which an LLM can get wrong or be overly optimistic about."""
    if not run_result.get("ok"):
        return False, run_result.get("error") or "specialist run failed"

    tool_calls = run_result.get("tool_calls") or []

    for call in tool_calls:
        result = call.get("result")
        if not isinstance(result, dict):
            continue
        if result.get("ok") is False:
            return False, f"tool '{call.get('name')}' failed: {result.get('error')}"
        if result.get("passed") is False:
            return False, f"tool '{call.get('name')}' reported failing tests"

    if role == "tester" and not any(c.get("name") in ("run_tests", "run_terminal") for c in tool_calls):
        return False, "tester made no run_tests/run_terminal calls — nothing was actually verified"

    return True, "all tool calls succeeded"


def _build_retry_note(attempt: int, reason: str, tool_calls: list) -> str:
    """Fed into the next attempt's prompt (see hub.agents.specialists.common
    .run_specialist_task's extra_context) so a retry tries something
    different instead of blindly repeating the same failing actions."""
    lines = [f"Attempt {attempt} failed: {reason}."]
    if tool_calls:
        lines.append("Tool calls made on that attempt:")
        for call in tool_calls[-5:]:
            result = call.get("result")
            call_ok = result.get("ok") if isinstance(result, dict) else None
            lines.append(f"- {call.get('name')}({call.get('args')}) -> ok={call_ok}")
    lines.append("Diagnose the underlying issue and fix it — don't just repeat the same actions.")
    return "\n".join(lines)


def _persist_attempt_log(
    project_id: str, task_id: str, attempt: int, role: str, run_result: dict, success: bool, reason: str
) -> None:
    """Best-effort: a logging failure must never fail the task itself."""
    log = {
        "task_id": task_id, "role": role, "attempt": attempt,
        "success": success, "reason": reason,
        "ok": run_result.get("ok"), "error": run_result.get("error"),
        "final_text": run_result.get("final_text"),
        "tool_calls": run_result.get("tool_calls"),
    }
    try:
        payload = json.dumps(log, indent=2, default=str)
        tools.write_file(project_id, f".agent_logs/{task_id}/attempt-{attempt}.json", payload)
    except Exception:
        pass


# ── Single task ──────────────────────────────────────────────────────────

async def run_task_async(
    task_id: str,
    project_id: Optional[str] = None,
    model: Optional[Union[str, BaseLlm]] = None,
    max_turns: Optional[int] = None,
    max_retries: Optional[int] = None,
) -> dict:
    """Run one task to completion (or exhaust its retries). Picks the
    specialist by the task spec's `role` field, builds context via
    spec_loader.build_agent_context (inside the specialist), runs the
    ADK loop, logs every attempt, updates status/board.json, and
    git-commits on success."""
    spec_path = spec_loader.find_task_spec_path(task_id)
    if spec_path is None:
        return _err(f"No task spec found for task_id: {task_id}", task_id=task_id)

    spec = spec_loader.load_spec(str(spec_path))
    if not spec.get("ok"):
        return {**spec, "task_id": task_id}
    if spec.get("type") not in ("task", "unknown"):
        return _err(f"{spec_path} is not a task spec (type={spec.get('type')})", path=str(spec_path), task_id=task_id)

    role = (spec.get("role") or "").strip().lower()
    if role not in ROLE_RUNNERS_ASYNC:
        return _err(f"Task {task_id} has an unknown or missing role: {spec.get('role')!r}", task_id=task_id)

    resolved_project_id = project_id or spec_loader.get_active_project_id()
    if not resolved_project_id:
        return _err("No project_id given and none found in project.meta.json", task_id=task_id)

    workspace_cfg = get_workspace_config()
    git_cfg = get_git_config()
    resolved_max_turns = max_turns or DEFAULT_MAX_TURNS
    resolved_max_retries = max(1, max_retries if max_retries is not None else workspace_cfg.get("retry_limit", 3))

    spec_loader.update_board_status(task_id, "in_progress", agent=role)

    run_fn = ROLE_RUNNERS_ASYNC[role]
    attempts: List[dict] = []
    last_result: dict = {}
    success = False
    reason = "not attempted"
    retry_note: Optional[str] = None

    for attempt_num in range(1, resolved_max_retries + 1):
        run_result = await run_fn(
            task_id,
            project_id=resolved_project_id,
            model=model,
            max_turns=resolved_max_turns,
            extra_context=retry_note,
        )
        success, reason = _determine_success(role, run_result)
        _persist_attempt_log(resolved_project_id, task_id, attempt_num, role, run_result, success, reason)

        attempts.append({
            "attempt": attempt_num,
            "success": success,
            "reason": reason,
            "tool_call_count": len(run_result.get("tool_calls") or []),
        })
        last_result = run_result

        if success:
            break
        retry_note = _build_retry_note(attempt_num, reason, run_result.get("tool_calls") or [])

    if success:
        commit_sha = None
        if git_cfg.get("auto_commit_on_success", True):
            prefix = git_cfg.get("commit_message_prefix", "[agent]")
            commit_result = tools.git_commit(resolved_project_id, f"{prefix} {task_id} ({role}): task complete")
            if commit_result.get("ok"):
                commit_sha = commit_result.get("commit_sha")

        spec_loader.update_board_status(task_id, "done", commit=commit_sha, agent=role)
        return _ok(
            task_id=task_id, role=role, feature=spec.get("feature"), status="done",
            attempts=attempts, attempt_count=len(attempts),
            final_text=last_result.get("final_text"), tool_calls=last_result.get("tool_calls"),
            commit_sha=commit_sha,
        )

    spec_loader.update_board_status(task_id, "failed", agent=role)
    return _err(
        f"Task {task_id} failed after {len(attempts)} attempt(s): {reason}",
        task_id=task_id, role=role, feature=spec.get("feature"), status="failed",
        attempts=attempts, attempt_count=len(attempts),
        final_text=last_result.get("final_text"), tool_calls=last_result.get("tool_calls"),
    )


def run_task(
    task_id: str,
    project_id: Optional[str] = None,
    model: Optional[Union[str, BaseLlm]] = None,
    max_turns: Optional[int] = None,
    max_retries: Optional[int] = None,
) -> dict:
    """Synchronous wrapper around run_task_async — the entry point for
    cli/main.py (`agent run --task T01`)."""
    return asyncio.run(
        run_task_async(task_id, project_id=project_id, model=model, max_turns=max_turns, max_retries=max_retries)
    )


# ── All pending tasks ────────────────────────────────────────────────────

async def run_pending_tasks_async(
    project_id: Optional[str] = None,
    model: Optional[Union[str, BaseLlm]] = None,
    max_turns: Optional[int] = None,
    max_retries: Optional[int] = None,
) -> dict:
    """Run every task currently 'pending' on status/board.json, in the
    order Feature Leads wrote them (which is dependency order, per their
    instruction — see hub/agents/feature_lead.py). Sequential, not
    parallel: simpler and avoids board.json write races."""
    resolved_project_id = project_id or spec_loader.get_active_project_id()
    if not resolved_project_id:
        return _err("No project_id given and none found in project.meta.json")

    pending = spec_loader.list_tasks(status="pending")
    if not pending:
        return _ok(project_id=resolved_project_id, task_count=0, results=[], done_count=0, failed_count=0)

    results = []
    for task in pending:
        task_id = task.get("id")
        if not task_id:
            continue
        result = await run_task_async(
            task_id, project_id=resolved_project_id, model=model, max_turns=max_turns, max_retries=max_retries
        )
        results.append(result)
        await asyncio.sleep(30)

    done_count = sum(1 for r in results if r.get("ok"))
    failed_count = len(results) - done_count

    return _ok(
        project_id=resolved_project_id,
        task_count=len(results),
        results=results,
        done_count=done_count,
        failed_count=failed_count,
    )


def run_pending_tasks(
    project_id: Optional[str] = None,
    model: Optional[Union[str, BaseLlm]] = None,
    max_turns: Optional[int] = None,
    max_retries: Optional[int] = None,
) -> dict:
    """Synchronous wrapper around run_pending_tasks_async — the entry
    point for cli/main.py (`agent run`, no --task given)."""
    return asyncio.run(
        run_pending_tasks_async(project_id=project_id, model=model, max_turns=max_turns, max_retries=max_retries)
    )
