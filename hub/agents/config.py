"""
hub/agents/config.py — shared config loader for hub/agents/

Reads config/agents.yaml so model names and limits (max_features,
max_tasks_per_feature, allowed_tools per specialist, retry_limit, ...)
live in one editable file rather than being hardcoded in agent modules.
Used by orchestrator.py, feature_lead.py, hub/agents/specialists/, and
hub/runner/task_runner.py.

ALSO: the vLLM/Gemini model router (resolve_model). Each agent builder
already does `model = explicit_override or cfg.get("model", <default>)`.
resolve_model() slots into that *second* branch only — an explicit
--model / API override still wins outright, exactly as before. When
there's no override, resolve_model() decides whether the role's
configured Gemini model name is actually used, or swapped for the
self-hosted vLLM endpoint, based on a cached health check.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Dict, Union

import httpx
import yaml
from google.adk.models.base_llm import BaseLlm

ROOT = Path(__file__).resolve().parent.parent.parent  # .../my-agent-hub
CONFIG_PATH = ROOT / "config" / "agents.yaml"

# Fallback defaults, used only if config/agents.yaml is missing or a key
# is absent — keeps agents usable even with a stripped-down config file.
_DEFAULTS: Dict[str, Any] = {
    "orchestrator": {"model": "gemini-2.5-pro", "max_features": 7},
    "feature_lead": {"model": "gemini-2.5-pro", "max_tasks_per_feature": 8},
    "eval_judge": {"model": "gemini-2.5-pro"},
    "specialists": {
        "explorer": {"model": "gemini-2.5-flash", "allowed_tools": ["read_file", "list_dir", "search_code"]},
        "coder": {"model": "gemini-2.5-flash", "allowed_tools": ["read_file", "write_file", "apply_patch", "search_code"]},
        "tester": {"model": "gemini-2.5-flash", "allowed_tools": ["read_file", "run_terminal", "run_tests"]},
        "reviewer": {"model": "gemini-2.5-flash", "allowed_tools": ["read_file", "search_code"]},
    },
    "workspace": {"retry_limit": 3},
    "rag": {"enabled": True, "top_k": 5},
    "git": {"auto_commit_on_success": True, "commit_message_prefix": "[agent]"},
}


# ── vLLM / Gemini model router ──────────────────────────────────────────
#
# Off by default: if VLLM_BASE_URL isn't set, resolve_model() is a no-op
# and every role behaves exactly as it did before (Gemini, per
# config/agents.yaml). Set VLLM_BASE_URL (e.g. in .env, once the EC2 box
# is up) to make the self-hosted model the default primary, with Gemini
# as the automatic fallback whenever the health check fails.
VLLM_BASE_URL = os.getenv("VLLM_BASE_URL", "").rstrip("/") or None
VLLM_API_KEY = os.getenv("VLLM_API_KEY")  # no hardcoded default — must be set explicitly
VLLM_MODEL = os.getenv("VLLM_MODEL", "Qwen/Qwen2.5-Coder-7B-Instruct")
VLLM_HEALTH_TIMEOUT_SECONDS = float(os.getenv("VLLM_HEALTH_TIMEOUT_SECONDS", "3"))
# Re-checked at most this often; a dead vLLM box shouldn't add a 3s
# timeout to every single agent build (orchestrator, every feature
# lead, every specialist call) — just to the first one in each window.
VLLM_HEALTH_CACHE_SECONDS = float(os.getenv("VLLM_HEALTH_CACHE_TTL", "30"))

_health_cache: Dict[str, Any] = {"healthy": False, "checked_at": 0.0}


def _vllm_health_url() -> str:
    # VLLM_BASE_URL is the OpenAI-compatible root (".../v1"); the
    # server's own health probe lives one level up.
    base = VLLM_BASE_URL[:-3] if VLLM_BASE_URL.endswith("/v1") else VLLM_BASE_URL
    return f"{base}/health"


def is_vllm_healthy(force: bool = False) -> bool:
    """Cached liveness check for the vLLM server. Returns False (never
    raises) on any network error, timeout, or non-200 — a flaky or
    unreachable box should just mean 'use the Gemini fallback', not a
    crash partway through planning or running a task."""
    if not VLLM_BASE_URL:
        return False
    now = time.monotonic()
    if not force and (now - _health_cache["checked_at"]) < VLLM_HEALTH_CACHE_SECONDS:
        return bool(_health_cache["healthy"])
    healthy = False
    try:
        resp = httpx.get(_vllm_health_url(), timeout=VLLM_HEALTH_TIMEOUT_SECONDS)
        healthy = resp.status_code == 200
    except Exception:
        healthy = False
    _health_cache["healthy"] = healthy
    _health_cache["checked_at"] = now
    return healthy


def get_model_router_status() -> Dict[str, Any]:
    """Small introspection helper for api.py's /api/model-status — lets
    the dashboard show which backend is actually serving requests right
    now, instead of that being invisible."""
    configured = bool(VLLM_BASE_URL)
    healthy = is_vllm_healthy() if configured else False
    return {
        "vllm_configured": configured,
        "vllm_base_url": VLLM_BASE_URL,
        "vllm_model": VLLM_MODEL if configured else None,
        "vllm_healthy": healthy,
        "active_backend": "vllm" if (configured and healthy) else "gemini",
    }


def resolve_model(default_model: str) -> Union[str, BaseLlm]:
    """The smart router. Call this where a role's *default* (non-override)
    model would otherwise be used:

        resolved_model = explicit_model_override or resolve_model(cfg.get("model", "..."))

    - VLLM_BASE_URL unset            -> returns default_model unchanged (Gemini, as before).
    - VLLM_BASE_URL set + healthy    -> returns a LiteLlm pointed at the vLLM server.
    - VLLM_BASE_URL set + unhealthy  -> returns default_model (Gemini fallback),
                                        preserving that role's own configured model
                                        (e.g. orchestrator can stay on a stronger
                                        model than the flash-tier specialists).
    """
    if not VLLM_BASE_URL or not is_vllm_healthy():
        return default_model
    if not VLLM_API_KEY:
        # Don't silently fall back here — a configured-but-keyless vLLM
        # setup is a config mistake worth surfacing, not masking.
        raise RuntimeError(
            "VLLM_BASE_URL is set but VLLM_API_KEY is missing. Set VLLM_API_KEY "
            "(matching the --api-key the vLLM server was started with) or unset "
            "VLLM_BASE_URL to use Gemini only."
        )
    try:
        # Lazy import: `litellm` is an optional extra
        # (`pip install google-adk[extensions]` or `litellm` directly).
        # Importing it eagerly at module load would force every caller
        # of config.py — including installs that never touch vLLM — to
        # have it installed. Only pay that cost once VLLM_BASE_URL is
        # actually set and the server is actually healthy.
        from google.adk.models.lite_llm import LiteLlm
    except ImportError as exc:
        raise RuntimeError(
            "VLLM_BASE_URL is set and the server is healthy, but the 'litellm' "
            "package isn't installed. Run: pip install litellm "
            "(or pip install google-adk[extensions])."
        ) from exc
    return LiteLlm(
        model=f"openai/{VLLM_MODEL}",
        api_base=VLLM_BASE_URL,
        api_key=VLLM_API_KEY,
    )


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


def get_rag_config() -> Dict[str, Any]:
    """The 'rag' block (enabled, top_k) controlling Phase 2's long-term
    memory retrieval — hub/memory/vector_store.py — merged over
    _DEFAULTS. `enabled: false` turns off both indexing completed work
    and injecting retrieved history into specialist prompts."""
    config = load_agents_config()
    merged = dict(_DEFAULTS["rag"])
    merged.update(config.get("rag", {}) or {})
    return merged
