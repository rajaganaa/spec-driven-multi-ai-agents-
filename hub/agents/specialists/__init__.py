"""
hub/agents/specialists/__init__.py — role -> runner dispatch table.

hub/runner/task_runner.py picks the right specialist for a task by its
spec's `role` field (explorer | coder | tester | reviewer) and calls the
matching entry here, rather than importing each module individually and
hand-writing an if/elif chain.
"""

from __future__ import annotations

from hub.agents.specialists import coder, explorer, reviewer, tester

ROLE_RUNNERS = {
    "explorer": explorer.run_explorer,
    "coder": coder.run_coder,
    "tester": tester.run_tester,
    "reviewer": reviewer.run_reviewer,
}

ROLE_RUNNERS_ASYNC = {
    "explorer": explorer.run_explorer_async,
    "coder": coder.run_coder_async,
    "tester": tester.run_tester_async,
    "reviewer": reviewer.run_reviewer_async,
}

ROLE_AGENT_BUILDERS = {
    "explorer": explorer.build_agent,
    "coder": coder.build_agent,
    "tester": tester.build_agent,
    "reviewer": reviewer.build_agent,
}

__all__ = ["ROLE_RUNNERS", "ROLE_RUNNERS_ASYNC", "ROLE_AGENT_BUILDERS"]
