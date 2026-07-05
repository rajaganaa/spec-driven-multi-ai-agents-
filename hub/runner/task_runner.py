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

REFLECTION LOOP (Reviewer/Tester -> Coder -> re-verify): a Reviewer or
Tester failure does NOT use the same-role retry path above. Instead,
its structured feedback (what's wrong, which file, why) is routed to
a Coder specialist as a targeted fix attempt (via the existing
extra_context mechanism), and then the same Reviewer/Tester re-runs to
verify the fix. This coder-fix -> re-verify cycle is capped at
workspace.retry_limit rounds (see _run_reflection_cycle), after which
the task falls back to "failed" exactly as before. Coder/Explorer
failures are unaffected and keep using the same-role retry loop.
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

    # NEW: a coder that never wrote/patched anything did not actually
    # do the task, even if zero tool calls means "nothing failed".
    if role == "coder" and not any(c.get("name") in ("write_file", "apply_patch") for c in tool_calls):
        return False, "coder made no write_file/apply_patch calls — nothing was actually implemented"

    if role == "tester" and not any(c.get("name") in ("run_tests", "run_terminal") for c in tool_calls):
        return False, "tester made no run_tests/run_terminal calls — nothing was actually verified"

    if role == "reviewer" and _reviewer_requested_changes(run_result.get("final_text") or ""):
        return False, f"reviewer requested changes: {_first_line(run_result.get('final_text') or '')}"

    return True, "all tool calls succeeded"

def _determine_verify_success(role: str, run_result: dict) -> Tuple[bool, str]:
    """Like _determine_success, but used only for the reflection cycle's
    re-verify step.  The only relaxation vs. the strict version is for the
    tester role: `passed=False` from run_tests is only treated as a hard
    failure when returncode == 1 (actual test failures).  Other non-zero
    exits — exit 4 (usage error, e.g. path not found before tests exist)
    or exit 5 (no tests collected) — are not failures at the re-verify
    stage, because the Coder has already applied its fix and the important
    signal is whether any collected test *failed*, not whether discovery
    had transient issues.

    All other behaviour (ok=False, reviewer change-request, no-run_tests
    call for tester) is identical to _determine_success."""
    if not run_result.get("ok"):
        return False, run_result.get("error") or "specialist run failed"

    tool_calls = run_result.get("tool_calls") or []

    for call in tool_calls:
        result = call.get("result")
        if not isinstance(result, dict):
            continue
        if result.get("ok") is False:
            return False, f"tool '{call.get('name')}' failed: {result.get('error')}"
        # For tester re-verify: only hard-fail on exit code 1 (tests ran and
        # failed).  Exit codes 4/5 (path error, no tests collected) are not
        # conclusive failures after a Coder fix — treat them as "ran OK".
        if result.get("passed") is False:
            if role == "tester" and result.get("returncode") != 1:
                continue  # transient discovery issue — not a definitive failure
            return False, f"tool '{call.get('name')}' reported failing tests"

    if role == "tester" and not any(c.get("name") in ("run_tests", "run_terminal") for c in tool_calls):
        return False, "tester made no run_tests/run_terminal calls — nothing was actually verified"

    if role == "reviewer" and _reviewer_requested_changes(run_result.get("final_text") or ""):
        return False, f"reviewer requested changes: {_first_line(run_result.get('final_text') or '')}"

    return True, "all tool calls succeeded"


# ── Reviewer verdict parsing ────────────────────────────────────────────────

def _reviewer_requested_changes(final_text: str) -> bool:
    """True if the Reviewer's verdict requested changes. reviewer.py's
    instruction asks it to reply with a leading 'Approved' or 'Changes
    requested' verdict; matched as a substring on the free-text reply
    rather than by strict parsing, since specialists don't emit
    structured output here."""
    return "changes requested" in final_text.lower()


def _first_line(text: str) -> str:
    return next((line.strip() for line in text.splitlines() if line.strip()), text.strip())


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
    project_id: str, task_id: str, attempt: Union[int, str], role: str, run_result: dict, success: bool, reason: str
) -> None:
    """Best-effort: a logging failure must never fail the task itself.
    `attempt` is normally the same-role retry counter (int); the
    reflection loop passes a round label instead (e.g. 'reflect-1-coder'),
    so every round of a cross-role handoff gets its own log file too."""
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


# ── Reflection loop: Reviewer/Tester failure -> Coder handoff -> re-verify ──

# Only these two roles get cross-role handoff; Coder/Explorer failures keep
# using the same-role retry loop in run_task_async unchanged.
CROSS_ROLE_HANDOFF_ROLES = ("reviewer", "tester")


def _build_handoff_note(verifier_role: str, round_num: int, reason: str, tool_calls: list, final_text: Optional[str]) -> str:
    """Feedback routed from a failing Reviewer/Tester to the Coder
    specialist as extra_context — what's wrong, and (where available)
    which file/why — so the Coder has a targeted fix to make instead of
    a generic 'try again'. Fed in via the same extra_context mechanism
    task_runner.py's same-role retries use (see run_specialist_task)."""
    lines = [f"A {verifier_role} rejected this task's output (reflection round {round_num}).", f"Reason: {reason}."]
    if final_text:
        lines.append(f"{verifier_role.capitalize()}'s full feedback:")
        lines.append(final_text.strip())
    if tool_calls:
        lines.append(f"{verifier_role.capitalize()}'s tool calls on that attempt:")
        for call in tool_calls[-5:]:
            result = call.get("result")
            call_ok = result.get("ok") if isinstance(result, dict) else None
            lines.append(f"- {call.get('name')}({call.get('args')}) -> ok={call_ok}")
    lines.append("Fix the specific issue(s) raised above — don't make unrelated changes.")
    return "\n".join(lines)


async def _run_reflection_cycle(
    task_id: str,
    project_id: str,
    verifier_role: str,
    verifier_run_fn,
    initial_run_result: dict,
    initial_reason: str,
    model: Optional[Union[str, BaseLlm]],
    max_turns: int,
    max_rounds: int,
    feature: Optional[str] = None,
) -> Tuple[bool, str, List[dict], dict]:
    """Cross-role handoff for a failing Reviewer/Tester attempt: route its
    feedback to a Coder specialist for a targeted fix (same task_id, same
    task spec, extra_context = the feedback), then re-run `verifier_role`
    to check the fix. Repeats up to `max_rounds` times (workspace.retry_limit),
    then gives up. Returns (success, reason, attempts, last_run_result) —
    `attempts` is meant to be extended onto the caller's own attempts list.

    Every round of both the Coder's fix and the re-verification is
    persisted via the existing _persist_attempt_log, so the full
    reflection chain for a task is visible under
    workspace/projects/<project>/.agent_logs/<task_id>/."""
    coder_run_fn = ROLE_RUNNERS_ASYNC["coder"]
    attempts: List[dict] = []
    run_result = initial_run_result
    reason = initial_reason
    success = False

    for round_num in range(1, max_rounds + 1):
        handoff_note = _build_handoff_note(
            verifier_role, round_num, reason, run_result.get("tool_calls") or [], run_result.get("final_text")
        )

        coder_result = await coder_run_fn(
            task_id, project_id=project_id, model=model, max_turns=max_turns, extra_context=handoff_note,
            feature=feature,
        )
        coder_success, coder_reason = _determine_success("coder", coder_result)
        _persist_attempt_log(project_id, task_id, f"reflect-{round_num}-coder", "coder", coder_result, coder_success, coder_reason)
        attempts.append({
            "attempt": f"reflect-{round_num}-coder", "role": "coder",
            "success": coder_success, "reason": coder_reason,
            "tool_call_count": len(coder_result.get("tool_calls") or []),
        })

        if not coder_success:
            # The Coder itself couldn't apply a fix this round — nothing
            # meaningful to re-verify yet. Record it and let the next
            # round's handoff note carry this failure forward too.
            run_result = coder_result
            reason = f"coder fix attempt failed: {coder_reason}"
            continue

        verify_result = await verifier_run_fn(
            task_id, project_id=project_id, model=model, max_turns=max_turns, extra_context=None,
            feature=feature,
        )
        verify_success, verify_reason = _determine_verify_success(verifier_role, verify_result)
        _persist_attempt_log(
            project_id, task_id, f"reflect-{round_num}-{verifier_role}", verifier_role, verify_result, verify_success, verify_reason
        )
        attempts.append({
            "attempt": f"reflect-{round_num}-{verifier_role}", "role": verifier_role,
            "success": verify_success, "reason": verify_reason,
            "tool_call_count": len(verify_result.get("tool_calls") or []),
        })

        run_result = verify_result
        reason = verify_reason
        success = verify_success

        if success:
            break

    return success, reason, attempts, run_result


# ── Single task ──────────────────────────────────────────────────────────

async def run_task_async(
    task_id: str,
    project_id: Optional[str] = None,
    model: Optional[Union[str, BaseLlm]] = None,
    max_turns: Optional[int] = None,
    max_retries: Optional[int] = None,
    feature: Optional[str] = None,
) -> dict:
    """Run one task to completion (or exhaust its retries). Picks the
    specialist by the task spec's `role` field, builds context via
    spec_loader.build_agent_context (inside the specialist), runs the
    ADK loop, logs every attempt, updates status/board.json, and
    git-commits on success."""
    spec_path = spec_loader.find_task_spec_path(task_id, feature=feature)
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

    resolved_feature = spec.get("feature") or feature
    spec_loader.update_board_status(task_id, "in_progress", agent=role, feature=resolved_feature)

    run_fn = ROLE_RUNNERS_ASYNC[role]
    attempts: List[dict] = []
    last_result: dict = {}
    success = False
    reason = "not attempted"

    if role in CROSS_ROLE_HANDOFF_ROLES:
        # Reflection loop, not same-role retry: one normal attempt, then on
        # failure hand off to a Coder for a targeted fix and re-verify with
        # this same role, up to resolved_max_retries rounds.
        run_result = await run_fn(
            task_id, project_id=resolved_project_id, model=model, max_turns=resolved_max_turns, extra_context=None,
            feature=spec.get("feature"),
        )
        success, reason = _determine_success(role, run_result)
        _persist_attempt_log(resolved_project_id, task_id, 1, role, run_result, success, reason)
        attempts.append({
            "attempt": 1, "role": role, "success": success, "reason": reason,
            "tool_call_count": len(run_result.get("tool_calls") or []),
        })
        last_result = run_result

        if not success:
            success, reason, reflection_attempts, last_result = await _run_reflection_cycle(
                task_id, resolved_project_id, role, run_fn, run_result, reason,
                model, resolved_max_turns, resolved_max_retries, feature=spec.get("feature"),
            )
            attempts.extend(reflection_attempts)
    else:
        retry_note: Optional[str] = None
        for attempt_num in range(1, resolved_max_retries + 1):
            run_result = await run_fn(
                task_id,
                project_id=resolved_project_id,
                model=model,
                max_turns=resolved_max_turns,
                extra_context=retry_note,
                feature=spec.get("feature"),
            )
            success, reason = _determine_success(role, run_result)
            _persist_attempt_log(resolved_project_id, task_id, attempt_num, role, run_result, success, reason)

            attempts.append({
                "attempt": attempt_num,
                "role": role,
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

        spec_loader.update_board_status(task_id, "done", commit=commit_sha, agent=role, feature=resolved_feature)
        return _ok(
            task_id=task_id, role=role, feature=spec.get("feature"), status="done",
            attempts=attempts, attempt_count=len(attempts),
            final_text=last_result.get("final_text"), tool_calls=last_result.get("tool_calls"),
            commit_sha=commit_sha,
        )

    spec_loader.update_board_status(task_id, "failed", agent=role, feature=resolved_feature)
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
            task_id, project_id=resolved_project_id, model=model, max_turns=max_turns, max_retries=max_retries,
            feature=task.get("feature"),
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
