"""
tests/fake_llm.py — a minimal google.adk.models.BaseLlm test double.

Lets tests drive a *real* ADK LlmAgent + Runner + InMemorySessionService
loop deterministically, with no network access and no API key: queue up
canned LlmResponse objects (or just JSON text, via from_json), and the
agent "calls the model" by popping the next one off the queue.

This is used to test hub/agents/orchestrator.py and feature_lead.py
end-to-end through real ADK machinery (structured output parsing,
session state, output_key wiring) rather than mocking ADK itself.
"""

from __future__ import annotations

import json
from typing import Any, List

from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.genai import types


class FakeLlm(BaseLlm):
    """model field is required by BaseLlm; pass any string. `turns` is a
    list of LlmResponse objects returned in order, one per model call."""

    turns: List[LlmResponse] = []
    calls: int = 0

    async def generate_content_async(self, llm_request, stream: bool = False):
        if self.calls >= len(self.turns):
            raise AssertionError(
                f"FakeLlm received more model calls ({self.calls + 1}) than turns queued ({len(self.turns)})"
            )
        response = self.turns[self.calls]
        self.calls += 1
        yield response


def text_turn(text: str) -> LlmResponse:
    """A single-turn model response that's just plain text."""
    return LlmResponse(content=types.Content(role="model", parts=[types.Part.from_text(text=text)]))


def json_turn(data: Any) -> LlmResponse:
    """A single-turn model response whose text is the JSON encoding of
    `data` — what a structured-output (output_schema) call returns."""
    return text_turn(json.dumps(data))
