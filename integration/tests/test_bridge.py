"""Tests for ``integration.bridge.translate_to_environment``."""

from __future__ import annotations

from schema import ParameterDelta, PolicyInterpretation, Source
from integration.bridge import BASELINE_ENVIRONMENT, translate_to_environment


def _interp(*deltas: ParameterDelta) -> PolicyInterpretation:
    return PolicyInterpretation(
        plain_english_summary="test",
        parameter_deltas=list(deltas),
        confidence=0.5,
        sources=[Source(title="t", url=None, excerpt="e")],
        reasoning_trace=["trace"],
        warnings=[],
    )


def test_trawling_reduces_fishing_pressure() -> None:
    interp = _interp(
        ParameterDelta(
            target="fishing_fleet.catch_rate",
            operation="multiply",
            value=0.35,
            rationale="commercial trawling ban",
        )
    )
    env = translate_to_environment(interp)
    assert env["fishing_pressure"] < BASELINE_ENVIRONMENT["fishing_pressure"]
    assert abs(env["fishing_pressure"] - 0.2 * 0.35) < 1e-9


def test_pollution_multiply_reduces_pollution_index() -> None:
    interp = _interp(
        ParameterDelta(
            target="ocean.pollution_index",
            operation="multiply",
            value=0.8,
            rationale="cleanup",
        )
    )
    env = translate_to_environment(interp)
    assert env["pollution_index"] < BASELINE_ENVIRONMENT["pollution_index"]
    assert abs(env["pollution_index"] - 0.3 * 0.8) < 1e-9


def test_empty_deltas_returns_baseline() -> None:
    interp = _interp()
    env = translate_to_environment(interp)
    for k in BASELINE_ENVIRONMENT:
        assert abs(env[k] - BASELINE_ENVIRONMENT[k]) < 1e-9


def test_clamp_extreme_multiply() -> None:
    interp = _interp(
        ParameterDelta(
            target="ocean.pollution_index",
            operation="multiply",
            value=100.0,
            rationale="extreme",
        )
    )
    env = translate_to_environment(interp)
    assert env["pollution_index"] == 1.0


def test_unknown_target_ignored() -> None:
    interp = _interp(
        ParameterDelta(
            target="ocean.dissolved_oxygen",
            operation="multiply",
            value=0.5,
            rationale="should skip mapping",
        ),
        ParameterDelta(
            target="anchovy.reproduction_rate",
            operation="multiply",
            value=2.0,
            rationale="should skip per spec",
        ),
    )
    env = translate_to_environment(interp)
    for k in BASELINE_ENVIRONMENT:
        assert abs(env[k] - BASELINE_ENVIRONMENT[k]) < 1e-9


def test_species_mortality_adjusts_fishing_pressure() -> None:
    interp = _interp(
        ParameterDelta(
            target="anchovy.mortality_rate",
            operation="multiply",
            value=0.75,
            rationale="lower mortality",
        )
    )
    env = translate_to_environment(interp)
    assert abs(env["fishing_pressure"] - 0.2 * 0.75) < 1e-9
