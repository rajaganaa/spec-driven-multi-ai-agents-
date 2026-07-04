"""
hub/eval/schemas.py — structured output schema for hub/eval/judge.py

Same design principle as hub/agents/schemas.py: the judge returns
validated structured data via ADK's output_schema (not free-form
markdown), so hub/eval/runner.py can compute pass/fail deterministically
in Python rather than trusting an LLM-authored verdict string that might
not actually agree with its own per-criterion scores.
"""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class CriterionScore(BaseModel):
    """The judge's verdict on one specific criterion (an acceptance
    criterion from the golden task, or a rubric item)."""

    criterion: str = Field(description="The exact criterion text being scored")
    passed: bool = Field(description="Whether the submitted work satisfies this criterion")
    comment: str = Field(default="", description="One sentence: why it passed or failed")


class JudgeVerdict(BaseModel):
    """LLM-as-judge's structured output for one golden task run.

    Deliberately has no top-level pass/fail field — hub/eval/runner.py
    derives that itself from criterion_scores (a task passes only if
    every acceptance-criterion CriterionScore has passed=True), so the
    pass/fail line is always consistent with the itemized scores instead
    of being a separately-hallucinated summary judgment."""

    criterion_scores: List[CriterionScore] = Field(min_length=1)
    overall_score: float = Field(ge=0.0, le=1.0, description="Holistic quality score, 0.0-1.0, independent of pass/fail")
    summary: str = Field(description="2-3 sentence overall assessment")
