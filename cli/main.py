"""
my-agent-hub CLI
================
`new` initializes a project; `plan` runs the Orchestrator (Part D) then
a Feature Lead per feature (Part D) to produce task specs; `run`
executes pending tasks via the task runner (Part E); `status` shows the
board.

DESIGN NOTE — why `plan` runs Orchestrator *and* Feature Lead, not `new`:
`new` is pure project setup — no LLM call, instant, no API key needed
yet. `plan` is the one command that walks goal -> features -> tasks, so
by the time it returns, `run` has something to execute. That matches
the usage sequence below and the Level 0/1/2 architecture: `plan`
covers Levels 0+1 (Orchestrator + Feature Leads), `run` covers Level 2
(Specialists, via the task runner).

Usage:
    python cli/main.py new "<goal>"
    python cli/main.py plan
    python cli/main.py run [--task TASK_ID] [--max-retries N]
    python cli/main.py status
"""

import json
import sys
from datetime import date
from pathlib import Path

import click
from rich.console import Console
from rich.markup import escape
from rich.table import Table

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from hub.agents import feature_lead, orchestrator  # noqa: E402
from hub.runner import task_runner  # noqa: E402

console = Console()

META_PATH = ROOT / "project.meta.json"
BOARD_PATH = ROOT / "status" / "board.json"


# ── Helpers ──────────────────────────────────────────────────────────────────

def _load_meta() -> dict:
    if not META_PATH.exists():
        console.print("[red]project.meta.json not found. Run `agent new` first.[/red]")
        sys.exit(1)
    return json.loads(META_PATH.read_text())


def _load_board() -> dict:
    if not BOARD_PATH.exists():
        return {"project_id": "", "updated_at": "", "tasks": []}
    return json.loads(BOARD_PATH.read_text())


# ── CLI group ─────────────────────────────────────────────────────────────────

@click.group()
def cli():
    """my-agent-hub — spec-driven multi-agent coding system."""
    pass


# ── new ───────────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("goal")
@click.option("--stack", default="python,fastapi", show_default=True,
              help="Comma-separated tech stack (e.g. python,fastapi,react)")
@click.option("--constraints", default="", help="Comma-separated constraints")
def new(goal: str, stack: str, constraints: str):
    """
    Start a new project from a plain-English GOAL.

    Example:
        python cli/main.py new "Build a HIPAA-aware medical FAQ chatbot"
    """
    project_id = f"project-{date.today().isoformat()}"
    meta = {
        "project_id": project_id,
        "goal": goal,
        "stack": [s.strip() for s in stack.split(",") if s.strip()],
        "constraints": [c.strip() for c in constraints.split(",") if c.strip()],
        "status": "planning",
        "created_at": date.today().isoformat(),
        "updated_at": date.today().isoformat(),
        "features": [],
        "notes": "",
    }
    META_PATH.write_text(json.dumps(meta, indent=2))
    BOARD_PATH.parent.mkdir(parents=True, exist_ok=True)
    BOARD_PATH.write_text(json.dumps({"project_id": project_id, "updated_at": "", "tasks": []}, indent=2))

    console.print(f"\n[bold green]✓ Project created:[/bold green] {project_id}")
    console.print(f"  Goal    : {escape(goal)}")
    console.print(f"  Stack   : {meta['stack']}")
    console.print("\n[dim]Next step → run: python cli/main.py plan[/dim]\n")


# ── plan ──────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--model", default=None, help="Override the model for this run (e.g. for cost control).")
def plan(model):
    """
    Run the Orchestrator to decompose the project goal into feature
    specs, then run a Feature Lead on each feature to produce task
    specs ready for `agent run`.

    Reads project.meta.json → writes specs/00-project-plan.md,
    specs/features/F*.md, specs/tasks/<feature>/T*.md, and registers
    every new task as "pending" on status/board.json.
    """
    meta = _load_meta()
    console.print(f"\n[bold]Planning project:[/bold] {meta['project_id']}")
    console.print(f"  Goal: {escape(meta['goal'])}\n")

    console.print("[cyan]→ Orchestrator: decomposing goal into features…[/cyan]")
    orch_result = orchestrator.run_orchestrator(meta["goal"], project_id=meta["project_id"], model=model)
    if not orch_result.get("ok"):
        console.print(f"[red]✗ Orchestrator failed:[/red] {escape(str(orch_result.get('error')))}\n")
        sys.exit(1)

    console.print(
        f"[green]✓[/green] {orch_result['feature_count']} feature(s) written: "
        f"{', '.join(orch_result['feature_ids'])}"
    )
    if orch_result.get("features_overflow"):
        console.print("[yellow]  (Orchestrator proposed more features than the configured max — extra ones were dropped)[/yellow]")
    console.print(f"  {orch_result.get('project_plan_path')}\n")

    console.print("[cyan]→ Feature Lead: breaking each feature into tasks…[/cyan]")
    total_tasks = 0
    any_failed = False
    for feature_id, feature_path in zip(orch_result["feature_ids"], orch_result["feature_spec_paths"]):
        fl_result = feature_lead.run_feature_lead(feature_path, project_id=meta["project_id"], model=model)
        if not fl_result.get("ok"):
            console.print(f"  [red]✗ {feature_id}:[/red] {escape(str(fl_result.get('error')))}")
            any_failed = True
            continue
        total_tasks += fl_result["task_count"]
        console.print(f"  [green]✓ {feature_id}:[/green] {fl_result['task_count']} task(s) — {', '.join(fl_result['task_ids'])}")
        if fl_result.get("tasks_overflow"):
            console.print(f"    [yellow](Feature Lead proposed more tasks than the configured max for {feature_id} — extras dropped)[/yellow]")

    console.print(f"\n[bold]{total_tasks} task(s) ready.[/bold] Next step → run: python cli/main.py run\n")
    if any_failed:
        sys.exit(1)


# ── run ───────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--task", default=None, help="Run a specific task ID (e.g. T01). Omit to run all pending.")
@click.option("--model", default=None, help="Override the model for this run (e.g. for cost control).")
@click.option("--max-retries", default=None, type=int, help="Override retry_limit from config/agents.yaml.")
def run(task, model, max_retries):
    """
    Execute pending tasks via specialist agents.

    Uses hub/runner/task_runner.py to pick the right specialist by role,
    build context, run the ADK tool-calling loop, retry on failure, and
    git-commit on success.
    """
    meta = _load_meta()

    if task:
        console.print(f"\n[bold]Running task:[/bold] {task}\n")
        result = task_runner.run_task(task, project_id=meta["project_id"], model=model, max_retries=max_retries)
        _print_task_result(result, fallback_task_id=task)
        if not result.get("ok"):
            sys.exit(1)
        return

    board = _load_board()
    pending = [t for t in board.get("tasks", []) if t.get("status") == "pending"]
    console.print(f"\n[bold]Running all pending tasks:[/bold] {len(pending)} found\n")

    if not pending:
        console.print("[dim]Nothing to run. `agent plan` first, or check `agent status`.[/dim]\n")
        return

    summary = task_runner.run_pending_tasks(project_id=meta["project_id"], model=model, max_retries=max_retries)
    for result in summary.get("results", []):
        _print_task_result(result)

    console.print(f"\n[bold]{summary['done_count']} done, {summary['failed_count']} failed[/bold] "
                  f"out of {summary['task_count']}.\n")
    if summary["failed_count"]:
        sys.exit(1)


def _print_task_result(result: dict, fallback_task_id: str = "?") -> None:
    task_id = escape(str(result.get("task_id") or fallback_task_id))
    role = escape(str(result.get("role") or "unknown role"))
    if result.get("ok"):
        commit = result.get("commit_sha")
        commit_note = f" (commit {escape(str(commit))})" if commit else " (nothing to commit)"
        console.print(f"  [green]✓ {task_id}[/green] ({role}) — done in {result.get('attempt_count', 1)} attempt(s){commit_note}")
    else:
        error = escape(str(result.get("error")))
        console.print(f"  [red]✗ {task_id}[/red] ({role}) — {error}")


# ── status ────────────────────────────────────────────────────────────────────

@cli.command()
def status():
    """
    Show the current task board (status/board.json).
    """
    meta = _load_meta()
    board = _load_board()
    tasks = board.get("tasks", [])

    console.print(f"\n[bold]Project:[/bold] {meta['project_id']}")
    console.print(f"[bold]Goal:[/bold]    {escape(meta['goal'])}\n")

    if not tasks:
        console.print("[dim]No tasks yet. Run `agent plan` first.[/dim]\n")
        return

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Task ID", style="dim", width=10)
    table.add_column("Feature", width=10)
    table.add_column("Status", width=14)
    table.add_column("Agent", width=12)
    table.add_column("Commit", width=10)

    status_colours = {
        "done": "green",
        "in_progress": "yellow",
        "pending": "white",
        "failed": "red",
    }

    for t in tasks:
        s = t.get("status", "pending")
        colour = status_colours.get(s, "white")
        commit = t.get("commit") or "—"
        table.add_row(
            t.get("id", ""),
            t.get("feature") or "—",
            f"[{colour}]{s}[/{colour}]",
            t.get("agent") or "—",
            commit,
        )

    console.print(table)
    console.print()


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cli()
