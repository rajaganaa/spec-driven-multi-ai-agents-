"""
hub/eval/runner.py — drives hub/eval/golden_tasks.py through the real
hub/runner/task_runner.py pipeline and scores each result with
hub/eval/judge.py.

IMPORTANT DESIGN NOTE — why this file exists instead of just calling
task_runner.run_task() directly for each golden task:

specs/, status/board.json, and project.meta.json are hub-level
singletons (see hub/memory/spec_loader.py's ROOT/SPECS_DIR/BOARD_PATH/
META_PATH — there is exactly one "active project" at a time, pointed to
by project.meta.json), NOT per-project. Simply writing golden task specs
alongside the user's real specs/ and running them would either collide
with real feature/task ids or silently redirect "the active project"
away from whatever the user is actually working on mid-run.

So run_eval_suite() below does NOT touch hub/runner/task_runner.py or
hub/memory/spec_loader.py's code — it only calls their existing public
functions, using a dedicated, clearly-namespaced project_id ("eval-
golden" by default) and a small snapshot/restore around the run:

  1. Back up the real project.meta.json + status/board.json bytes (if
     they exist).
  2. Point them at the eval project temporarily.
  3. Write golden task specs into a dedicated, clearly-namespaced
     subtree (specs/features/FEVAL-*.md, specs/tasks/EVAL/*.md) that
     cannot collide with real F##/T## ids.
  4. Run every golden task through the real pipeline, in a workspace
     sandbox scoped to the eval project_id (workspace/projects/eval-
     golden/ by default) — completely separate from the user's real
     project's sandbox.
  5. In a `finally`: restore the original meta.json/board.json bytes
     (or delete them if they didn't exist before), and delete the
     golden spec files this run wrote. The user's real specs/, board,
     and project sandbox are untouched by the time this returns —
     whether it succeeded, failed, or raised.

This is why run_eval_suite() should not be called concurrently with any
other operation that reads/writes project.meta.json or status/board.json
(e.g. don't run `agent run` and `agent eval` in the same process at the
same time) — same "no concurrency" assumption already made elsewhere in
this hub (see run_pending_tasks_async's sequential-with-sleep design).
"""

from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path
from typing import List, Optional, Union

from google.adk.models.base_llm import BaseLlm

from hub.eval.golden_tasks import GOLDEN_TASKS, GoldenTask
from hub.eval.judge import run_judge_async
from hub.memory import spec_loader
from hub.runner import task_runner
from hub.tools import tools

DEFAULT_EVAL_PROJECT_ID = "eval-golden"
EVAL_FEATURE_ID = "FEVAL"
EVAL_TASKS_SUBDIR = "EVAL"


def _ok(**kwargs) -> dict:
    return {"ok": True, "error": None, **kwargs}


def _err(message: str, **kwargs) -> dict:
    return {"ok": False, "error": message, **kwargs}


# ── Rendering golden tasks into real spec markdown ──────────────────────────

def _render_list(items: list) -> str:
    return "\n".join(f"- {i}" for i in items) if items else "(none)"


def _render_checklist(items: list) -> str:
    return "\n".join(f"- [ ] {c}" for c in items) if items else "- [ ] (none specified)"


def _render_feature_md() -> str:
    return (
        f"# {EVAL_FEATURE_ID}: Golden Evaluation Suite\n\n"
        "## Goal\nFixed set of golden tasks used by hub/eval/runner.py to evaluate specialist quality.\n\n"
        "## Acceptance Criteria\n- [ ] (n/a — this feature exists only to host eval tasks)\n\n"
        "## Files Likely Touched\n(varies per task)\n\n"
        "## Dependencies\n(none)\n\n"
        "## Assigned Lead\neval-runner\n\n"
        "## Status\nplanning\n"
    )


def _render_task_md(task: GoldenTask) -> str:
    return (
        f"# {task.id}: {task.title}\n\n"
        f"## Feature\n{EVAL_FEATURE_ID}\n\n"
        f"## Role\n{task.role}\n\n"
        f"## Goal\n{task.goal}\n\n"
        f"## Context Files (max 5)\n{_render_list(task.context_files)}\n\n"
        f"## Instructions\n{task.instructions}\n\n"
        f"## Acceptance Criteria\n{_render_checklist(task.acceptance_criteria)}\n\n"
        f"## Definition of Done\n{_render_list(task.definition_of_done)}\n\n"
        "## Status\npending\n"
    )


# ── Snapshot / restore of hub-level singleton state ─────────────────────────

class _HubStateSnapshot:
    """Backs up project.meta.json + status/board.json bytes on enter,
    restores them (or removes them if they didn't exist before) on
    exit — regardless of whether the eval run succeeded, failed, or
    raised. See this module's docstring for why this is necessary."""

    def __init__(self) -> None:
        self._meta_backup: Optional[bytes] = None
        self._board_backup: Optional[bytes] = None

    def __enter__(self) -> "_HubStateSnapshot":
        self._meta_backup = spec_loader.META_PATH.read_bytes() if spec_loader.META_PATH.exists() else None
        self._board_backup = spec_loader.BOARD_PATH.read_bytes() if spec_loader.BOARD_PATH.exists() else None
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._meta_backup is not None:
            spec_loader.META_PATH.write_bytes(self._meta_backup)
        elif spec_loader.META_PATH.exists():
            spec_loader.META_PATH.unlink()

        if self._board_backup is not None:
            spec_loader.BOARD_PATH.write_bytes(self._board_backup)
        elif spec_loader.BOARD_PATH.exists():
            spec_loader.BOARD_PATH.unlink()


def _point_active_project_at(project_id: str) -> None:
    spec_loader.META_PATH.parent.mkdir(parents=True, exist_ok=True)
    spec_loader.META_PATH.write_text(
        json.dumps({"project_id": project_id, "goal": "hub/eval golden task suite", "stack": [], "constraints": []}),
        encoding="utf-8",
    )
    spec_loader.BOARD_PATH.parent.mkdir(parents=True, exist_ok=True)
    spec_loader.BOARD_PATH.write_text(
        json.dumps({"project_id": project_id, "updated_at": "", "tasks": []}), encoding="utf-8",
    )


def _write_golden_specs(golden_tasks: List[GoldenTask]) -> Path:
    """Writes the eval feature spec + one task spec per golden task.
    Returns the tasks subdirectory path, so cleanup can remove exactly
    what was written here."""
    spec_loader.FEATURES_DIR.mkdir(parents=True, exist_ok=True)
    (spec_loader.FEATURES_DIR / f"{EVAL_FEATURE_ID}-golden-eval-suite.md").write_text(
        _render_feature_md(), encoding="utf-8",
    )

    tasks_subdir = spec_loader.TASKS_DIR / EVAL_TASKS_SUBDIR
    tasks_subdir.mkdir(parents=True, exist_ok=True)
    for task in golden_tasks:
        (tasks_subdir / f"{task.id}-{task.title.lower().replace(' ', '-')[:30]}.md").write_text(
            _render_task_md(task), encoding="utf-8",
        )
    return tasks_subdir


def _cleanup_golden_specs(tasks_subdir: Path) -> None:
    shutil.rmtree(tasks_subdir, ignore_errors=True)
    feature_path = spec_loader.FEATURES_DIR / f"{EVAL_FEATURE_ID}-golden-eval-suite.md"
    feature_path.unlink(missing_ok=True)


def _seed_context_files(project_id: str, task: GoldenTask) -> Optional[dict]:
    """Write any files a golden task's instructions assume already
    exist (a bug to fix, code to test/review). Returns an error dict if
    a write fails, else None."""
    for rel_path, content in task.seed_files.items():
        result = tools.write_file(project_id, rel_path, content)
        if not result.get("ok"):
            return result
    return None


def _diff_text_for(project_id: str, commit_sha: Optional[str]) -> Optional[str]:
    """Best-effort `git show` for the judge's benefit — mirrors
    hub/memory/spec_loader.py's _index_completed_task, but a failure
    here should never block scoring, just means the judge grades
    without seeing the diff."""
    if not commit_sha:
        return None
    result = tools.run_terminal(project_id, f"git show {commit_sha}")
    return result.get("stdout") if result.get("ok") else None


# ── Main entry point ─────────────────────────────────────────────────────

async def run_eval_suite_async(
    golden_tasks: Optional[List[GoldenTask]] = None,
    project_id: str = DEFAULT_EVAL_PROJECT_ID,
    model: Optional[Union[str, BaseLlm]] = None,
    judge_model: Optional[Union[str, BaseLlm]] = None,
    max_retries: Optional[int] = None,
    keep_workspace: bool = False,
) -> dict:
    """Run every golden task through the real specialist pipeline and
    score each with the LLM-as-judge. Returns a summary plus a full
    per-task breakdown. See this module's docstring for the isolation
    guarantees around the user's real active project.

    `model`/`judge_model` accept an explicit BaseLlm override (e.g. a
    FakeLlm in tests) exactly like every other run_*_async entry point
    in this hub — production callers normally leave these as None and
    let config/agents.yaml + resolve_model() decide."""
    tasks = golden_tasks if golden_tasks is not None else GOLDEN_TASKS
    if not tasks:
        return _err("golden_tasks is empty — nothing to evaluate")

    results: List[dict] = []

    with _HubStateSnapshot():
        _point_active_project_at(project_id)
        tasks_subdir = _write_golden_specs(tasks)

        proj_dir = tools.WORKSPACE_ROOT / project_id
        if proj_dir.exists() and not keep_workspace:
            shutil.rmtree(proj_dir, ignore_errors=True)

        try:
            for task in tasks:
                seed_error = _seed_context_files(project_id, task)
                if seed_error is not None:
                    results.append({
                        "task_id": task.id, "title": task.title, "role": task.role,
                        "run": seed_error, "judge": _err(f"Skipped judging: seeding failed: {seed_error.get('error')}"),
                    })
                    continue

                effective_max_retries = 1 if task.expect_rejection else max_retries
                run_result = await task_runner.run_task_async(
                    task.id, project_id=project_id, model=model, max_retries=effective_max_retries,
                )
                run_result = dict(run_result)

                # A reviewer correctly rejecting bad code is the intended
                # outcome for this task, not an infra failure — don't let
                # the retry-failure status hide a good review from the judge.
                if (task.expect_rejection and not run_result.get("ok")
                        and "reviewer requested changes" in (run_result.get("error") or "")):
                    run_result["ok"] = True
                    run_result["error"] = None

                run_result["diff_text"] = _diff_text_for(project_id, run_result.get("commit_sha"))

                judge_result = await run_judge_async(task, run_result, model=judge_model)
                results.append({"task_id": task.id, "title": task.title, "role": task.role,
                                 "run": run_result, "judge": judge_result})
        finally:
            _cleanup_golden_specs(tasks_subdir)
            if not keep_workspace and proj_dir.exists():
                shutil.rmtree(proj_dir, ignore_errors=True)

    passed_count = sum(1 for r in results if r["judge"].get("ok") and r["judge"].get("passed"))
    judged = [r for r in results if r["judge"].get("ok")]
    avg_score = (sum(r["judge"]["overall_score"] for r in judged) / len(judged)) if judged else 0.0

    return _ok(
        project_id=project_id,
        task_count=len(tasks),
        passed_count=passed_count,
        failed_count=len(tasks) - passed_count,
        judged_count=len(judged),
        judge_error_count=len(tasks) - len(judged),
        avg_overall_score=avg_score,
        results=results,
    )


def run_eval_suite(
    golden_tasks: Optional[List[GoldenTask]] = None,
    project_id: str = DEFAULT_EVAL_PROJECT_ID,
    model: Optional[Union[str, BaseLlm]] = None,
    judge_model: Optional[Union[str, BaseLlm]] = None,
    max_retries: Optional[int] = None,
    keep_workspace: bool = False,
) -> dict:
    """Synchronous wrapper around run_eval_suite_async — the entry
    point for cli/main.py (`agent eval`)."""
    return asyncio.run(
        run_eval_suite_async(
            golden_tasks, project_id=project_id, model=model, judge_model=judge_model,
            max_retries=max_retries, keep_workspace=keep_workspace,
        )
    )
