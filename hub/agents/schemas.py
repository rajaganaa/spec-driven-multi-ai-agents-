"""
hub/agents/schemas.py — structured output schemas for the planning agents
(Part D: Orchestrator, Feature Lead).

DESIGN NOTE: why structured output instead of a write_file tool
-------------------------------------------------------------------
Orchestrator and Feature Lead could be given a write_file-style tool and
asked to produce raw markdown matching the spec template themselves —
but spec_loader.py (Part C) depends on that markdown being exactly
right, and LLM-formatted markdown is not reliably exact. Instead, these
agents use ADK's `output_schema` to return validated structured data
(see google.adk.agents.LlmAgent(output_schema=..., output_key=...)),
and hub/agents/orchestrator.py / feature_lead.py render that data into
the exact markdown template deterministically in Python before writing
it via hub.tools.tools.write_spec_file(). "Tools do real work; the LLM
decides" still holds — the LLM decides *what* the plan/features/tasks
are; Python guarantees *how* they're persisted is always parseable.
"""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class FeaturePlanItem(BaseModel):
    """One feature, as proposed by the Orchestrator."""

    id: str = Field(description="Feature id, e.g. 'F01' (sequential, zero-padded to 2 digits)")
    title: str = Field(description="Short feature title, e.g. 'Authentication'")
    goal: str = Field(description="One sentence: what this feature delivers")
    acceptance_criteria: List[str] = Field(min_length=1, description="Concrete, checkable acceptance criteria")
    files_likely_touched: List[str] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list, description="Other feature ids this depends on, if any")
    assigned_lead: str = Field(default="feature-lead")


class ProjectPlan(BaseModel):
    """Orchestrator's structured output: the whole project decomposition."""

    goal: str = Field(description="Restated user goal")
    summary: str = Field(description="2-4 sentence summary of the overall approach")
    features: List[FeaturePlanItem] = Field(min_length=1)


class TaskPlanItem(BaseModel):
    """One task, as proposed by a Feature Lead."""

    id: str = Field(description="Task id, e.g. 'T01' (sequential within the feature)")
    title: str = Field(description="Short task title, e.g. 'User model + DB schema'")
    role: str = Field(description="One of: explorer | coder | tester | reviewer")
    goal: str = Field(description="One sentence: what this task implements")
    context_files: List[str] = Field(
        default_factory=list,
        description="At most 5 paths a specialist needs to read to do this task "
        "(spec paths like 'specs/features/F01-x.md' or project paths like 'src/x.py')",
    )
    instructions: str = Field(description="Step-by-step instructions for the specialist agent")
    acceptance_criteria: List[str] = Field(min_length=1, description="Concrete, checkable acceptance criteria")
    definition_of_done: List[str] = Field(default_factory=list)


class FeatureTaskPlan(BaseModel):
    """Feature Lead's structured output: one feature broken into tasks."""

    feature: str = Field(description="The feature id these tasks belong to, e.g. 'F01'")
    tasks: List[TaskPlanItem] = Field(min_length=1)
