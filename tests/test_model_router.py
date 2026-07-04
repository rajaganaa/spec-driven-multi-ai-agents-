"""
tests/test_model_router.py — Part 2: vLLM / Gemini model router

Covers hub/agents/config.py's resolve_model() / is_vllm_healthy() /
get_model_router_status(): the off-by-default behavior, the cached
health check, the healthy-vLLM path, and the unhealthy-vLLM fallback.
Does NOT touch a real network — httpx.get is monkeypatched throughout.
"""

from __future__ import annotations

import importlib

import pytest

from hub.agents import config as cfg_module


@pytest.fixture(autouse=True)
def _reset_router_state(monkeypatch):
    """Each test gets a clean slate: no VLLM_BASE_URL, empty health
    cache, and the module reloaded so the env-derived constants
    (VLLM_BASE_URL, VLLM_API_KEY, ...) are re-read fresh."""
    monkeypatch.delenv("VLLM_BASE_URL", raising=False)
    monkeypatch.delenv("VLLM_API_KEY", raising=False)
    importlib.reload(cfg_module)
    yield
    importlib.reload(cfg_module)


def test_resolve_model_is_noop_when_vllm_unset():
    """No VLLM_BASE_URL configured -> router doesn't touch the network
    at all and returns the role's configured Gemini model unchanged."""
    assert cfg_module.resolve_model("gemini-2.5-flash") == "gemini-2.5-flash"
    assert cfg_module.is_vllm_healthy() is False


def test_resolve_model_falls_back_when_vllm_unhealthy(monkeypatch):
    monkeypatch.setenv("VLLM_BASE_URL", "http://10.0.0.5:8000/v1")
    monkeypatch.setenv("VLLM_API_KEY", "test-key")
    importlib.reload(cfg_module)

    def _boom(*args, **kwargs):
        raise ConnectionError("vLLM box is down")

    monkeypatch.setattr(cfg_module.httpx, "get", _boom)

    assert cfg_module.is_vllm_healthy() is False
    # Falls back to the role's own configured Gemini model, not a
    # hardcoded one-size-fits-all default.
    assert cfg_module.resolve_model("gemini-2.5-pro") == "gemini-2.5-pro"


def test_resolve_model_returns_litellm_when_vllm_healthy(monkeypatch):
    pytest.importorskip("litellm")  # optional extra — skip cleanly if absent
    monkeypatch.setenv("VLLM_BASE_URL", "http://10.0.0.5:8000/v1")
    monkeypatch.setenv("VLLM_API_KEY", "test-key")
    importlib.reload(cfg_module)

    class _FakeResp:
        status_code = 200

    monkeypatch.setattr(cfg_module.httpx, "get", lambda *a, **k: _FakeResp())

    from google.adk.models.lite_llm import LiteLlm

    result = cfg_module.resolve_model("gemini-2.5-flash")
    assert isinstance(result, LiteLlm)
    assert result.model == "openai/Qwen/Qwen2.5-Coder-7B-Instruct"


def test_resolve_model_raises_on_missing_api_key(monkeypatch):
    monkeypatch.setenv("VLLM_BASE_URL", "http://10.0.0.5:8000/v1")
    monkeypatch.delenv("VLLM_API_KEY", raising=False)
    importlib.reload(cfg_module)

    class _FakeResp:
        status_code = 200

    monkeypatch.setattr(cfg_module.httpx, "get", lambda *a, **k: _FakeResp())

    with pytest.raises(RuntimeError, match="VLLM_API_KEY"):
        cfg_module.resolve_model("gemini-2.5-flash")


def test_health_check_is_cached(monkeypatch):
    monkeypatch.setenv("VLLM_BASE_URL", "http://10.0.0.5:8000/v1")
    monkeypatch.setenv("VLLM_API_KEY", "test-key")
    importlib.reload(cfg_module)

    calls = {"n": 0}

    class _FakeResp:
        status_code = 200

    def _counting_get(*args, **kwargs):
        calls["n"] += 1
        return _FakeResp()

    monkeypatch.setattr(cfg_module.httpx, "get", _counting_get)

    cfg_module.is_vllm_healthy()
    cfg_module.is_vllm_healthy()
    cfg_module.is_vllm_healthy()
    assert calls["n"] == 1, "second/third call within the TTL should hit the cache, not the network"

    cfg_module.is_vllm_healthy(force=True)
    assert calls["n"] == 2, "force=True should bypass the cache"


def test_get_model_router_status_shape(monkeypatch):
    monkeypatch.setenv("VLLM_BASE_URL", "http://10.0.0.5:8000/v1")
    monkeypatch.setenv("VLLM_API_KEY", "test-key")
    importlib.reload(cfg_module)
    monkeypatch.setattr(cfg_module.httpx, "get", lambda *a, **k: (_ for _ in ()).throw(ConnectionError()))

    status = cfg_module.get_model_router_status()
    assert status["vllm_configured"] is True
    assert status["vllm_healthy"] is False
    assert status["active_backend"] == "gemini"
