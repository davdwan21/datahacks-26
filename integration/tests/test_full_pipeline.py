"""Tests for ``integration.run_full_pipeline.run_policy_simulation``."""

from __future__ import annotations

import asyncio

import pytest

from integration.bridge import BASELINE_ENVIRONMENT
from integration.run_full_pipeline import run_policy_simulation

_SPECIES_KEYS = (
    "phytoplankton",
    "zooplankton",
    "anchovy",
    "sardine",
    "sea_lion",
    "kelp",
    "urchin",
)


def _fake_snapshots(environment: dict, num_ticks: int = 5) -> list[dict]:
    """Deterministic snapshots (35× Groq per full run is too slow for default pytest)."""
    return [
        {
            "tick": i + 1,
            "species": {
                name: {
                    "population": 50,
                    "last_action": "stub",
                    "health_trend": "stable",
                    "behavior": "stub",
                    "reason": "stub",
                }
                for name in _SPECIES_KEYS
            },
        }
        for i in range(num_ticks)
    ]


@pytest.fixture(autouse=True)
def _clear_demo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEMO_MODE", raising=False)
    yield


def test_demo_mode_trawling_pressure_and_snapshots(monkeypatch: pytest.MonkeyPatch) -> None:
    import integration.run_full_pipeline as rfp

    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setattr(rfp, "run_simulation", _fake_snapshots)

    policy = "Ban commercial trawling within 50 miles of California coast"
    out = asyncio.run(run_policy_simulation(policy, num_ticks=5, region="socal"))

    assert out.get("error") is None
    assert out["environment_after_policy"]["fishing_pressure"] < BASELINE_ENVIRONMENT["fishing_pressure"]
    assert len(out["simulation_snapshots"]) == 5
    for snap in out["simulation_snapshots"]:
        assert len(snap["species"]) == 7


def test_same_policy_twice_independent_snapshots(monkeypatch: pytest.MonkeyPatch) -> None:
    import integration.run_full_pipeline as rfp

    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setattr(rfp, "run_simulation", _fake_snapshots)

    policy = "Ban commercial trawling within 50 miles of California coast"

    r1 = asyncio.run(run_policy_simulation(policy, num_ticks=3, region="socal"))
    r2 = asyncio.run(run_policy_simulation(policy, num_ticks=3, region="socal"))

    assert r1.get("error") is None and r2.get("error") is None
    assert r1["simulation_snapshots"] is not r2["simulation_snapshots"]
    assert r1["simulation_snapshots"][0] is not r2["simulation_snapshots"][0]
