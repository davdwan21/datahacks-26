"""Tests for schema validation (Step 1 contract)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from schema import ParameterDelta, PolicyInterpretation, Source


def test_valid_policy_interpretation() -> None:
    interp = PolicyInterpretation(
        plain_english_summary="Test policy reduces fishing pressure.",
        parameter_deltas=[
            ParameterDelta(
                target="anchovy.mortality_rate",
                operation="multiply",
                value=0.9,
                rationale="Lower fishing mortality under a trawl restriction.",
            )
        ],
        confidence=0.75,
        sources=[
            Source(
                title="Example study",
                url="https://example.org/paper",
                excerpt="Fisheries closures reduce target species mortality.",
            )
        ],
        reasoning_trace=["Parsed intent.", "Grounded in literature."],
        warnings=[],
    )
    assert interp.confidence == 0.75
    assert len(interp.parameter_deltas) == 1
    assert interp.parameter_deltas[0].target == "anchovy.mortality_rate"


def test_invalid_target_rejected() -> None:
    with pytest.raises(ValidationError) as exc:
        ParameterDelta(
            target="invalid.entity.field",
            operation="multiply",
            value=1.0,
            rationale="Should fail validation.",
        )
    assert "target" in str(exc.value).lower() or "Invalid parameter" in str(exc.value)


def test_invalid_operation_rejected() -> None:
    with pytest.raises(ValidationError) as exc:
        ParameterDelta(
            target="ocean.ph",
            operation="divide",
            value=1.0,
            rationale="divide is not a valid operation.",
        )
    assert "operation" in str(exc.value).lower() or "Invalid operation" in str(exc.value)


def test_confidence_out_of_range_rejected() -> None:
    with pytest.raises(ValidationError):
        PolicyInterpretation(
            plain_english_summary="x",
            parameter_deltas=[
                ParameterDelta(
                    target="fishing_fleet.catch_rate",
                    operation="set",
                    value=0.5,
                    rationale="r",
                )
            ],
            confidence=1.5,
            sources=[],
            reasoning_trace=["a"],
            warnings=[],
        )
