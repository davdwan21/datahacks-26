"""Tests for ``integration.orchestrator.run_simulation`` (ticks stubbed — no live Groq)."""

from __future__ import annotations

import copy

import pytest

from integration.bridge import BASELINE_ENVIRONMENT


def _tick_return(agent: dict) -> tuple[dict, str, str]:
    """Return a fresh agent dict and fixed behavior/reason (no LLM)."""
    a = copy.deepcopy(agent)
    a.setdefault("population", 50)
    a["last_action"] = "stub"
    a["health_trend"] = "stable"
    return a, "stub_act", "stub reason"


def _install_stub_ticks(monkeypatch: pytest.MonkeyPatch) -> None:
    import integration.orchestrator as orch

    monkeypatch.setattr(orch, "phyto_tick", lambda agent, env: _tick_return(agent))
    monkeypatch.setattr(orch, "zooplankton_tick", lambda agent, env, phyto: _tick_return(agent))
    monkeypatch.setattr(orch, "anchovy_tick", lambda agent, env, zoo: _tick_return(agent))
    monkeypatch.setattr(orch, "sardine_tick", lambda agent, env, zoo, anchovy: _tick_return(agent))
    monkeypatch.setattr(orch, "sealion_tick", lambda agent, env, anchovy, sardine: _tick_return(agent))
    monkeypatch.setattr(orch, "kelp_tick", lambda agent, env, urchin_prev: _tick_return(agent))
    monkeypatch.setattr(orch, "urchin_tick", lambda agent, env, kelp_prev: _tick_return(agent))


def test_five_ticks_seven_species(monkeypatch: pytest.MonkeyPatch) -> None:
    import integration.orchestrator as orch

    _install_stub_ticks(monkeypatch)
    snaps = orch.run_simulation(dict(BASELINE_ENVIRONMENT), num_ticks=5)
    assert len(snaps) == 5
    for s in snaps:
        assert set(s["species"].keys()) == {
            "phytoplankton",
            "zooplankton",
            "anchovy",
            "sardine",
            "sea_lion",
            "kelp",
            "urchin",
        }


def test_populations_clamped_zero_to_hundred(monkeypatch: pytest.MonkeyPatch) -> None:
    import integration.orchestrator as orch

    _install_stub_ticks(monkeypatch)
    snaps = orch.run_simulation(dict(BASELINE_ENVIRONMENT), num_ticks=5)
    for s in snaps:
        for name, block in s["species"].items():
            pop = block["population"]
            assert 0 <= pop <= 100, f"{name} population {pop} out of range"


def test_two_runs_independent_no_shared_mutation(monkeypatch: pytest.MonkeyPatch) -> None:
    import integration.orchestrator as orch
    from integration.Layer2.phytoplankton import agent as phy_mod

    _install_stub_ticks(monkeypatch)
    a = orch.run_simulation(dict(BASELINE_ENVIRONMENT), num_ticks=2)
    b = orch.run_simulation(dict(BASELINE_ENVIRONMENT), num_ticks=2)
    assert a is not b
    assert a[0] is not b[0]
    assert phy_mod["population"] == 65


def test_kelp_tick_receives_urchin_pre_tick_state(monkeypatch: pytest.MonkeyPatch) -> None:
    import integration.orchestrator as orch
    from integration.Layer2.urchin import urchin as urchin_module_state

    _install_stub_ticks(monkeypatch)
    captured: list[dict] = []

    real_kelp_stub = orch.kelp_tick

    def kelp_spy(kelp_agent, env, urchin_prev):
        captured.append(copy.deepcopy(urchin_prev))
        return real_kelp_stub(kelp_agent, env, urchin_prev)

    monkeypatch.setattr(orch, "kelp_tick", kelp_spy)

    urchin_before_run = copy.deepcopy(urchin_module_state)
    snaps = orch.run_simulation(dict(BASELINE_ENVIRONMENT), num_ticks=2)

    assert len(captured) == 2
    assert captured[0] == dict(urchin_before_run)
    prev_urchin = {k: v for k, v in snaps[0]["species"]["urchin"].items() if k not in ("behavior", "reason")}
    assert captured[1] == prev_urchin
