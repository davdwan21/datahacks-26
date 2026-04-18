"""Pydantic I/O contract for policy interpretation (single source of truth)."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, field_validator

from valid_parameters import VALID_OPERATIONS, VALID_TARGETS


class PolicyRequest(BaseModel):
    """Input from the frontend."""

    policy_text: str
    region: str = "socal"


class ParameterDelta(BaseModel):
    """One simulation parameter change proposed from a policy."""

    target: str
    operation: str
    value: float
    rationale: str

    @field_validator("target")
    @classmethod
    def target_must_be_valid(cls, v: str) -> str:
        if v not in VALID_TARGETS:
            raise ValueError(f"Invalid parameter target: {v!r}; must be one of the approved sim keys.")
        return v

    @field_validator("operation")
    @classmethod
    def operation_must_be_valid(cls, v: str) -> str:
        if v not in VALID_OPERATIONS:
            raise ValueError(
                f"Invalid operation: {v!r}; must be one of {sorted(VALID_OPERATIONS)}."
            )
        return v


class Source(BaseModel):
    """Citation or reference supporting the interpretation."""

    title: str
    url: Optional[str] = None
    excerpt: str


class PolicyInterpretation(BaseModel):
    """Full response returned from POST /interpret."""

    plain_english_summary: str
    parameter_deltas: list[ParameterDelta]
    confidence: float = Field(..., ge=0.0, le=1.0)
    sources: list[Source]
    reasoning_trace: list[str]
    warnings: list[str]
