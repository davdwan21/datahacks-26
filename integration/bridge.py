"""Translate Layer 1 ``PolicyInterpretation`` into Layer 2 environment scalars."""

from __future__ import annotations

from typing import Any

from schema import PolicyInterpretation

BASELINE_ENVIRONMENT: dict[str, float] = {
    "temperature": 16.2,
    "nutrients": 0.6,
    "pH": 8.05,
    "salinity": 33.4,
    "fishing_pressure": 0.2,
    "pollution_index": 0.3,
}

CLAMP_RANGES: dict[str, tuple[float, float]] = {
    "temperature": (10.0, 22.0),
    "nutrients": (0.0, 1.0),
    "pH": (7.8, 8.4),
    "salinity": (30.0, 36.0),
    "fishing_pressure": (0.0, 1.0),
    "pollution_index": (0.0, 1.0),
}

_MORTALITY_SPECIES: frozenset[str] = frozenset(
    {"anchovy", "sardine", "sea_lion", "leopard_shark", "market_squid", "pelican"}
)


def _apply_op(current: float, op: str, value: float) -> float:
    if op == "multiply":
        return current * value
    if op == "add":
        return current + value
    if op == "set":
        return value
    return current


def _clamp_environment(env: dict[str, float]) -> dict[str, float]:
    out: dict[str, float] = {}
    for key, val in env.items():
        lo, hi = CLAMP_RANGES[key]
        out[key] = max(lo, min(hi, float(val)))
    return out


def translate_to_environment(
    interpretation: PolicyInterpretation,
    baseline: dict[str, float] | None = None,
) -> dict[str, float]:
    """
    Apply ``interpretation.parameter_deltas`` to a baseline environment dict.

    Unknown targets are skipped. Values are clamped to ``CLAMP_RANGES``.
    """
    base = dict(baseline) if baseline is not None else dict(BASELINE_ENVIRONMENT)
    env: dict[str, float] = {k: float(v) for k, v in base.items()}

    for delta in interpretation.parameter_deltas:
        target = delta.target
        op = delta.operation
        value = float(delta.value)

        if target == "fishing_fleet.catch_rate":
            env["fishing_pressure"] = _apply_op(env["fishing_pressure"], op, value)
        elif target == "fishing_fleet.effort_level":
            env["fishing_pressure"] = _apply_op(env["fishing_pressure"], op, value)
        elif target == "ocean.pollution_index":
            env["pollution_index"] = _apply_op(env["pollution_index"], op, value)
        elif target == "coastal_community.runoff_rate":
            env["pollution_index"] = _apply_op(env["pollution_index"], op, value)
            env["nutrients"] = _apply_op(env["nutrients"], op, value)
        elif target == "ocean.temperature":
            env["temperature"] = _apply_op(env["temperature"], op, value)
        elif target == "ocean.nutrient_level":
            env["nutrients"] = _apply_op(env["nutrients"], op, value)
        elif target == "ocean.ph":
            env["pH"] = _apply_op(env["pH"], op, value)
        elif target == "ocean.dissolved_oxygen":
            continue
        elif target == "protected_area.coverage_percent":
            if op == "set":
                env["fishing_pressure"] = 0.2 * (1.0 - value / 100.0)
            else:
                continue
        elif target.endswith(".reproduction_rate"):
            continue
        elif target.endswith(".mortality_rate"):
            prefix = target[: -len(".mortality_rate")]
            if prefix in _MORTALITY_SPECIES:
                env["fishing_pressure"] = _apply_op(env["fishing_pressure"], op, value)
        else:
            continue

    return _clamp_environment(env)
