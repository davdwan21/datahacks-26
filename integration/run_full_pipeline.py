"""End-to-end: Layer 1 policy interpretation → bridge → Layer 2 simulation."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_repo = Path(__file__).resolve().parent.parent
_layer1 = _repo / "Layer1"
for p in (_layer1, _repo):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

try:
    from dotenv import load_dotenv

    load_dotenv(_layer1 / ".env")
except ImportError:
    pass

from integration.bridge import translate_to_environment
from integration.orchestrator import run_simulation
from pipeline import interpret_policy
from schema import PolicyRequest


async def run_policy_simulation(
    policy_text: str,
    num_ticks: int = 5,
    region: str = "socal",
) -> dict[str, Any]:
    """
    Interpret ``policy_text``, translate to environment scalars, run Layer 2 ticks.

    On failure, returns the same top-level keys with ``error`` set and empty/null payloads
    so callers always get a JSON-serializable object.
    """
    try:
        request = PolicyRequest(policy_text=policy_text, region=region)
        interpretation = await interpret_policy(request)
        environment = translate_to_environment(interpretation)
        snapshots = run_simulation(environment, num_ticks=num_ticks)
        return {
            "policy_interpretation": interpretation.model_dump(),
            "environment_after_policy": environment,
            "simulation_snapshots": snapshots,
            "num_ticks": num_ticks,
            "error": None,
        }
    except Exception as err:
        return {
            "policy_interpretation": None,
            "environment_after_policy": None,
            "simulation_snapshots": [],
            "num_ticks": num_ticks,
            "error": f"{type(err).__name__}: {err}",
        }
