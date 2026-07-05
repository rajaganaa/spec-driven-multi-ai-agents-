def patch_file(path, edits):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    for old, new, name in edits:
        if old not in content:
            raise SystemExit(f"[{path}] edit \x27{name}\x27 NOT FOUND -- aborting, no changes written to this file")
        content = content.replace(old, new, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Patched {path}: {len(edits)} edit(s) OK")


# 1. spec_loader.py: build_agent_context needs a feature param
patch_file("hub/memory/spec_loader.py", [
(
"""def build_agent_context(
    task_id: str,
    max_files: int = MAX_CONTEXT_FILES,
    max_tokens: int = MAX_CONTEXT_TOKENS,
) -> dict:
    \"\"\"Given a task id, load its task spec plus (up to max_files) listed
    context files, capped at ~max_tokens total. Returns a dict that is
    the specialist agent's entire prompt context \u2014 nothing else, no
    chat history. No LLM calls.\"\"\"
    spec_path = find_task_spec_path(task_id)""",
"""def build_agent_context(
    task_id: str,
    max_files: int = MAX_CONTEXT_FILES,
    max_tokens: int = MAX_CONTEXT_TOKENS,
    feature: Optional[str] = None,
) -> dict:
    \"\"\"Given a task id, load its task spec plus (up to max_files) listed
    context files, capped at ~max_tokens total. Returns a dict that is
    the specialist agent's entire prompt context -- nothing else, no
    chat history. No LLM calls.

    Pass feature whenever known: task IDs (T01, T02...) restart at 1 for
    every feature, so without it this silently loads whichever feature's
    same-numbered task sorts first alphabetically -- the specialist then
    receives a COMPLETELY WRONG spec/instructions with no indication
    anything is wrong (this was a real, serious bug: an F17 React task
    was silently handed F14's FastAPI-backend instructions instead).\"\"\"
    spec_path = find_task_spec_path(task_id, feature=feature)""",
"build_agent_context: add feature param + pass through"
),
])

# 2. common.py: run_specialist_task needs a feature param, forwarded to build_agent_context
patch_file("hub/agents/specialists/common.py", [
(
"""async def run_specialist_task(
    role: str,
    build_agent_fn: Callable[..., LlmAgent],
    task_id: str,
    project_id: Optional[str] = None,
    model: Optional[Union[str, BaseLlm]] = None,
    max_turns: int = DEFAULT_MAX_TURNS,
    extra_context: Optional[str] = None,
) -> dict:""",
"""async def run_specialist_task(
    role: str,
    build_agent_fn: Callable[..., LlmAgent],
    task_id: str,
    project_id: Optional[str] = None,
    model: Optional[Union[str, BaseLlm]] = None,
    max_turns: int = DEFAULT_MAX_TURNS,
    extra_context: Optional[str] = None,
    feature: Optional[str] = None,
) -> dict:""",
"run_specialist_task: add feature param"
),
(
"""    context = spec_loader.build_agent_context(task_id)""",
"""    context = spec_loader.build_agent_context(task_id, feature=feature)""",
"run_specialist_task: pass feature into build_agent_context"
),
])

# 3-6. Each specialist wrapper: add feature param, forward it
for fname in ("coder", "tester", "reviewer", "explorer"):
    path = f"hub/agents/specialists/{fname}.py"
    patch_file(path, [
    (
    """    max_turns: int = DEFAULT_MAX_TURNS,
    extra_context: Optional[str] = None,
) -> dict:
    return await run_specialist_task(
        ROLE, build_agent, task_id, project_id=project_id, model=model,
        max_turns=max_turns, extra_context=extra_context,
    )""",
    """    max_turns: int = DEFAULT_MAX_TURNS,
    extra_context: Optional[str] = None,
    feature: Optional[str] = None,
) -> dict:
    return await run_specialist_task(
        ROLE, build_agent, task_id, project_id=project_id, model=model,
        max_turns=max_turns, extra_context=extra_context, feature=feature,
    )""",
    f"run_{fname}_async: add feature param + forward"
    ),
    ])

# 7. task_runner.py: thread feature through _run_reflection_cycle and both run_fn call sites
patch_file("hub/runner/task_runner.py", [
(
"""async def _run_reflection_cycle(
    task_id: str,
    project_id: str,
    verifier_role: str,
    verifier_run_fn,
    initial_run_result: dict,
    initial_reason: str,
    model: Optional[Union[str, BaseLlm]],
    max_turns: int,
    max_rounds: int,
) -> Tuple[bool, str, List[dict], dict]:""",
"""async def _run_reflection_cycle(
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
) -> Tuple[bool, str, List[dict], dict]:""",
"_run_reflection_cycle: add feature param"
),
(
"""        coder_result = await coder_run_fn(
            task_id, project_id=project_id, model=model, max_turns=max_turns, extra_context=handoff_note,
        )""",
"""        coder_result = await coder_run_fn(
            task_id, project_id=project_id, model=model, max_turns=max_turns, extra_context=handoff_note,
            feature=feature,
        )""",
"_run_reflection_cycle: pass feature to coder_run_fn"
),
(
"""        verify_result = await verifier_run_fn(
            task_id, project_id=project_id, model=model, max_turns=max_turns, extra_context=None,
        )""",
"""        verify_result = await verifier_run_fn(
            task_id, project_id=project_id, model=model, max_turns=max_turns, extra_context=None,
            feature=feature,
        )""",
"_run_reflection_cycle: pass feature to verifier_run_fn"
),
(
"""        run_result = await run_fn(
            task_id, project_id=resolved_project_id, model=model, max_turns=resolved_max_turns, extra_context=None,
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
                model, resolved_max_turns, resolved_max_retries,
            )""",
"""        run_result = await run_fn(
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
            )""",
"run_task_async: pass feature in cross-role-handoff branch"
),
(
"""            run_result = await run_fn(
                task_id,
                project_id=resolved_project_id,
                model=model,
                max_turns=resolved_max_turns,
                extra_context=retry_note,
            )""",
"""            run_result = await run_fn(
                task_id,
                project_id=resolved_project_id,
                model=model,
                max_turns=resolved_max_turns,
                extra_context=retry_note,
                feature=spec.get("feature"),
            )""",
"run_task_async: pass feature in same-role retry loop branch"
),
])

print()
print("ALL PATCHES APPLIED SUCCESSFULLY.")
