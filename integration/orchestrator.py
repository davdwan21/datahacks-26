"""Layer 2 species orchestration: run all seven ticks per round in dependency order."""

from __future__ import annotations

import copy
import os
from typing import Any

if not os.environ.get("GROQ_API_KEY", "").strip():
    raise RuntimeError(
        "GROQ_API_KEY is not set or is empty. Add it to Layer1/.env (or export it in your shell) "
        "before importing the Layer 2 orchestrator; Groq is required for all seven species ticks."
    )

from integration.Layer2.anchovy import anchovy as anchovy_template
from integration.Layer2.anchovy import tick as anchovy_tick
from integration.Layer2.kelp import kelp as kelp_template
from integration.Layer2.kelp import tick as kelp_tick
from integration.Layer2.phytoplankton import agent as phyto_agent_template
from integration.Layer2.phytoplankton import tick as phyto_tick
from integration.Layer2.sardine import sardine as sardine_template
from integration.Layer2.sardine import tick as sardine_tick
from integration.Layer2.sealion import sea_lion as sealion_template
from integration.Layer2.sealion import tick as sealion_tick
from integration.Layer2.urchin import urchin as urchin_template
from integration.Layer2.urchin import tick as urchin_tick
from integration.Layer2.zooplankton import tick as zooplankton_tick
from integration.Layer2.zooplankton import zooplankton as zooplankton_template


def run_simulation(
    environment: dict[str, float],
    num_ticks: int = 5,
    initial_state: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """
    Run Layer 2 species ticks for ``num_ticks`` rounds.

    Uses ``copy.deepcopy`` of module-level agent templates so repeated runs do not
    mutate imported module state. Kelp and urchin each read the other's **pre-tick**
    shallow-copy dict for that round before either is updated.
    """
    env = copy.deepcopy(environment)

    phyto: dict[str, Any] = copy.deepcopy(phyto_agent_template)
    zoo: dict[str, Any] = copy.deepcopy(zooplankton_template)
    anchovy: dict[str, Any] = copy.deepcopy(anchovy_template)
    sardine: dict[str, Any] = copy.deepcopy(sardine_template)
    sealion: dict[str, Any] = copy.deepcopy(sealion_template)
    kelp: dict[str, Any] = copy.deepcopy(kelp_template)
    urchin: dict[str, Any] = copy.deepcopy(urchin_template)

    if initial_state:
        for key, state in initial_state.items():
            if key == "phytoplankton":
                phyto = copy.deepcopy(state)
            elif key == "zooplankton":
                zoo = copy.deepcopy(state)
            elif key == "anchovy":
                anchovy = copy.deepcopy(state)
            elif key == "sardine":
                sardine = copy.deepcopy(state)
            elif key == "sea_lion":
                sealion = copy.deepcopy(state)
            elif key == "kelp":
                kelp = copy.deepcopy(state)
            elif key == "urchin":
                urchin = copy.deepcopy(state)

    snapshots: list[dict[str, Any]] = []

    for tick_num in range(1, num_ticks + 1):
        phyto, phyto_behavior, phyto_reason = phyto_tick(phyto, env)
        zoo, zoo_behavior, zoo_reason = zooplankton_tick(zoo, env, phyto)
        anchovy, anchovy_behavior, anchovy_reason = anchovy_tick(anchovy, env, zoo)
        sardine, sardine_behavior, sardine_reason = sardine_tick(sardine, env, zoo, anchovy)
        sealion, sealion_behavior, sealion_reason = sealion_tick(sealion, env, anchovy, sardine)

        kelp_prev = dict(kelp)
        urchin_prev = dict(urchin)
        kelp, kelp_behavior, kelp_reason = kelp_tick(kelp, env, urchin_prev)
        urchin, urchin_behavior, urchin_reason = urchin_tick(urchin, env, kelp_prev)

        snapshots.append(
            {
                "tick": tick_num,
                "species": {
                    "phytoplankton": {**phyto, "behavior": phyto_behavior, "reason": phyto_reason},
                    "zooplankton": {**zoo, "behavior": zoo_behavior, "reason": zoo_reason},
                    "anchovy": {**anchovy, "behavior": anchovy_behavior, "reason": anchovy_reason},
                    "sardine": {**sardine, "behavior": sardine_behavior, "reason": sardine_reason},
                    "sea_lion": {**sealion, "behavior": sealion_behavior, "reason": sealion_reason},
                    "kelp": {**kelp, "behavior": kelp_behavior, "reason": kelp_reason},
                    "urchin": {**urchin, "behavior": urchin_behavior, "reason": urchin_reason},
                },
            }
        )

    return snapshots
