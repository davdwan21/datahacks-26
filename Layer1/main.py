"""FastAPI entrypoint for Layer 1 policy interpretation."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

_repo_root = Path(__file__).resolve().parents[1]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from integration.run_full_pipeline import run_policy_simulation

from pipeline import interpret_policy
from schema import PolicyInterpretation, PolicyRequest

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s %(message)s",
)

class SimulateRequest(BaseModel):
    """Body for ``POST /simulate`` (Layer 1 + Layer 2 full run)."""

    policy_text: str
    region: str = "socal"
    num_ticks: int = Field(default=5, ge=1, le=50)


app = FastAPI(title="Layer 1 Policy Interpreter", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/interpret", response_model=PolicyInterpretation)
async def interpret(request: PolicyRequest) -> PolicyInterpretation:
    return await interpret_policy(request)


@app.post("/simulate")
async def simulate(body: SimulateRequest) -> dict:
    return await run_policy_simulation(
        body.policy_text,
        num_ticks=body.num_ticks,
        region=body.region,
    )
