"""
hub/agents/config.py — shared config loader for hub/agents/

Reads config/agents.yaml so model names and limits (max_features,
max_tasks_per_feature, allowed_tools per specialist, retry_limit, ...)
live in one editable file rather than being hardcoded in agent modules.
Used by orchestrator.py, feature_lead.py, hub/agents/specialists/, and
hub/runner/task_runner.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent  # .../my-agent-hub
CONFIG_PATH = ROOT / "config" / "agents.yaml"

# Fallback defaults, used only if config/agents.yaml is missing or a key
# is absent — keeps agents usable even with a stripped-down config file.
_DEFAULTS: Dict[str, Any] = {
    "orchestrator": {"model": "gemini-2.5-pro", "max_features": 7},
    "feature_lead": {"model": "gemini-2.5-pro", "max_tasks_per_feature": 8},
    "specialists": {
        "explorer": {"model": "gemini-2.5-flash", "allowed_tools": ["read_file", "list_dir", "search_code"]},
        "coder": {"model": "gemini-2.5-flash", "allowed_tools": ["read_file", "write_file", "apply_patch", "search_code"]},
        "tester": {"model": "gemini-2.5-flash", "allowed_tools": ["read_file", "run_terminal", "run_tests"]},
        "reviewer": {"model": "gemini-2.5-flash", "allowed_tools": ["read_file", "search_code"]},
    },
    "workspace": {"retry_limit": 3},
    "git": {"auto_commit_on_success": True, "commit_message_prefix": "[agent]"},
}


def load_agents_config() -> Dict[str, Any]:
    """Parse config/agents.yaml. Returns {} (not an error) if the file
    is missing, so callers can fall back to _DEFAULTS via get_agent_config."""
    if not CONFIG_PATH.exists():
        return {}
    try:
        data = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def get_agent_config(agent_key: str) -> Dict[str, Any]:
    """Config block for one agent (e.g. 'orchestrator', 'feature_lead'),
    merged over _DEFAULTS so missing keys still have sane fallbacks."""
    config = load_agents_config()
    merged = dict(_DEFAULTS.get(agent_key, {}))
    merged.update(config.get(agent_key, {}) or {})
    return merged


def get_specialist_config(role: str) -> Dict[str, Any]:
    """Config block for one Level 2 specialist (explorer/coder/tester/
    reviewer): model + allowed_tools, merged over _DEFAULTS."""
    config = load_agents_config()
    merged = dict(_DEFAULTS["specialists"].get(role, {}))
    merged.update((config.get("specialists", {}) or {}).get(role, {}) or {})
    return merged


def get_workspace_config() -> Dict[str, Any]:
    """The 'workspace' block (retry_limit, ...), merged over _DEFAULTS."""
    config = load_agents_config()
    merged = dict(_DEFAULTS["workspace"])
    merged.update(config.get("workspace", {}) or {})
    return merged


def get_git_config() -> Dict[str, Any]:
    """The 'git' block (auto_commit_on_success, commit_message_prefix),
    merged over _DEFAULTS."""
    config = load_agents_config()
    merged = dict(_DEFAULTS["git"])
    merged.update(config.get("git", {}) or {})
    return merged
