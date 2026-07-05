import re

def patch_file(path, edits):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    for i, (old, new, name) in enumerate(edits):
        if old not in content:
            raise SystemExit(f"[{path}] edit '{name}' NOT FOUND -- aborting, no changes written to this file")
        content = content.replace(old, new, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Patched {path}: {len(edits)} edit(s) OK")


# -- 1 & 2: hub/memory/spec_loader.py ----------------------------------------
patch_file("hub/memory/spec_loader.py", [
(
'''def find_task_spec_path(task_id: str) -> Optional[Path]:
    """Locate a task spec file by id, searching both the documented
    nested layout (specs/tasks/<feature>/T*.md) and the flat layout
    used by the current scaffold example (specs/tasks/T*.md)."""
    if not TASKS_DIR.exists() or not task_id:
        return None

    candidates: List[Path] = []''',
'''def find_task_spec_path(task_id: str, feature: Optional[str] = None) -> Optional[Path]:
    """Locate a task spec file by id, searching both the documented
    nested layout (specs/tasks/<feature>/T*.md) and the flat layout
    used by the current scaffold example (specs/tasks/T*.md).

    Task IDs (T01, T02...) restart at 1 for EVERY feature, so they are
    not globally unique -- without a feature hint this is inherently
    ambiguous across a multi-feature project and silently returns
    whichever feature happens to sort first alphabetically. Pass
    feature whenever it's known to get a correct, deterministic match.
    """
    if not TASKS_DIR.exists() or not task_id:
        return None

    if feature:
        feature_dir = TASKS_DIR / feature
        if feature_dir.exists():
            scoped = sorted(
                p for p in feature_dir.glob("*.md")
                if p.stem.lower().startswith(task_id.lower())
            )
            if scoped:
                return scoped[0]

    candidates: List[Path] = []''',
"find_task_spec_path: add feature param + scoped search"
),
(
'''def update_board_status(
    task_id: str,
    status: str,
    commit: Optional[str] = None,
    agent: Optional[str] = None,
) -> dict:''',
'''def update_board_status(
    task_id: str,
    status: str,
    commit: Optional[str] = None,
    agent: Optional[str] = None,
    feature: Optional[str] = None,
) -> dict:''',
"update_board_status: add feature param to signature"
),
(
'''    tasks = board["tasks"]
    entry = next((t for t in tasks if isinstance(t, dict) and t.get("id") == task_id), None)
    created = entry is None

    if entry is None:
        feature = None
        spec_path = find_task_spec_path(task_id)
        if spec_path is not None:
            spec = load_spec(str(spec_path))
            if spec.get("ok"):
                feature = spec.get("feature")
        entry = {"id": task_id, "feature": feature, "status": status, "agent": agent, "commit": commit}
        tasks.append(entry)''',
'''    tasks = board["tasks"]
    # Task IDs restart at T01 for every feature -- match on (id, feature)
    # together whenever feature is known, or a same-numbered task from a
    # DIFFERENT feature silently clobbers this one's board entry (the
    # real bug: a later feature's T01 was overwriting an earlier
    # feature's already-"done" T01 entry).
    if feature:
        entry = next(
            (t for t in tasks if isinstance(t, dict) and t.get("id") == task_id and t.get("feature") == feature),
            None,
        )
    else:
        entry = next((t for t in tasks if isinstance(t, dict) and t.get("id") == task_id), None)
    created = entry is None

    if entry is None:
        resolved_feature = feature
        if resolved_feature is None:
            spec_path = find_task_spec_path(task_id)
            if spec_path is not None:
                spec = load_spec(str(spec_path))
                if spec.get("ok"):
                    resolved_feature = spec.get("feature")
        entry = {"id": task_id, "feature": resolved_feature, "status": status, "agent": agent, "commit": commit}
        tasks.append(entry)''',
"update_board_status: scope entry lookup by (id, feature)"
),
])

# -- 3 & 4: hub/runner/task_runner.py -----------------------------------------
patch_file("hub/runner/task_runner.py", [
(
'''async def run_task_async(
    task_id: str,
    project_id: Optional[str] = None,
    model: Optional[Union[str, BaseLlm]] = None,
    max_turns: Optional[int] = None,
    max_retries: Optional[int] = None,
) -> dict:''',
'''async def run_task_async(
    task_id: str,
    project_id: Optional[str] = None,
    model: Optional[Union[str, BaseLlm]] = None,
    max_turns: Optional[int] = None,
    max_retries: Optional[int] = None,
    feature: Optional[str] = None,
) -> dict:''',
"run_task_async: add feature param"
),
(
'''    spec_path = spec_loader.find_task_spec_path(task_id)
    if spec_path is None:
        return _err(f"No task spec found for task_id: {task_id}", task_id=task_id)''',
'''    spec_path = spec_loader.find_task_spec_path(task_id, feature=feature)
    if spec_path is None:
        return _err(f"No task spec found for task_id: {task_id}", task_id=task_id)''',
"run_task_async: pass feature into find_task_spec_path"
),
(
'''    spec_loader.update_board_status(task_id, "in_progress", agent=role)''',
'''    resolved_feature = spec.get("feature") or feature
    spec_loader.update_board_status(task_id, "in_progress", agent=role, feature=resolved_feature)''',
"run_task_async: resolve feature + pass to in_progress update"
),
(
'''        spec_loader.update_board_status(task_id, "done", commit=commit_sha, agent=role)''',
'''        spec_loader.update_board_status(task_id, "done", commit=commit_sha, agent=role, feature=resolved_feature)''',
"run_task_async: pass feature to done update"
),
(
'''    spec_loader.update_board_status(task_id, "failed", agent=role)''',
'''    spec_loader.update_board_status(task_id, "failed", agent=role, feature=resolved_feature)''',
"run_task_async: pass feature to failed update"
),
(
'''    for task in pending:
        task_id = task.get("id")
        if not task_id:
            continue
        result = await run_task_async(
            task_id, project_id=resolved_project_id, model=model, max_turns=max_turns, max_retries=max_retries
        )''',
'''    for task in pending:
        task_id = task.get("id")
        if not task_id:
            continue
        result = await run_task_async(
            task_id, project_id=resolved_project_id, model=model, max_turns=max_turns, max_retries=max_retries,
            feature=task.get("feature"),
        )''',
"run_pending_tasks_async: pass feature hint from board entry"
),
])

# -- 5: hub/agents/feature_lead.py --------------------------------------------
patch_file("hub/agents/feature_lead.py", [
(
'''        board_result = spec_loader.update_board_status(item.id, "pending")''',
'''        board_result = spec_loader.update_board_status(item.id, "pending", feature=feature_id)''',
"feature_lead: register board entries scoped to their real feature"
),
])

print()
print("ALL PATCHES APPLIED SUCCESSFULLY.")
