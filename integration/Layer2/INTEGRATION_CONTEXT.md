# Layer 1 ↔ Layer 2 Integration Context

> Read this entire file before writing any code.

## Project Background

Hackathon project: natural-language policy → ecosystem simulation.
- Layer 1 (complete, in `/Layer1/`) interprets policies with multi-agent LLM pipeline
- Layer 2 (species files in `/integration/layer2/`) has 7 LLM species agents
- **IMPORTANT: Layer 2 has NO orchestrator.** Species files run standalone. You must build the orchestrator as part of this integration.

## The Three Pieces to Build

1. **Orchestrator** — runs all 7 Layer 2 species per tick in dependency order
2. **Bridge** — translates Layer 1 parameter_deltas → Layer 2 environment dict
3. **Full pipeline** — wires Layer 1 → Bridge → Orchestrator → snapshots

## Layer 2 Species Files (in `/integration/layer2/`)

Each file defines a tick function and a module-level agent state. They do NOT import each other. They expect neighbor states to be passed in as arguments.

| File | Tick signature | Reads |
|---|---|---|
| phytoplankton.py | `tick(agent, environment)` | env only |
| zooplankton.py | `tick(zoo, env, phytoplankton_state)` | env + phyto |
| anchovy.py | `tick(agent, env, zooplankton_state)` | env + zoo |
| sardine.py | `tick(agent, env, zooplankton_state, anchovy_state)` | env + zoo + anchovy |
| sealion.py | `tick(agent, env, anchovy_state, sardine_state)` | env + anchovy + sardine |
| kelp.py | `tick(agent, env, urchin_state)` | env + urchin |
| urchin.py | `tick(agent, env, kelp_state)` | env + kelp |

Note: kelp ↔ urchin is a mutual pair. On tick N, both read each other's tick N-1 state. For the first tick, use the module-level initial states.

### Return values
Each tick returns `(updated_agent_dict, behavior_string, reason_string)`.

### Agent state shape
```python
{"population": int 0-100, "last_action": str, "health_trend": str}
```

### Critical Layer 2 dependencies
- Uses Groq API (not Gemini). Needs `GROQ_API_KEY` in `.env`.
- Each tick = 1 LLM call per species. 7 species × 5 ticks = 35 LLM calls per run.
- Groq free tier handles this fine.

## Layer 1 Interface (in `/Layer1/`)

- FastAPI endpoint `POST /interpret` returns `PolicyInterpretation`
- Key field: `parameter_deltas: List[ParameterDelta]`
- Each `ParameterDelta`: `{target: str, operation: str, value: float, rationale: str}`
- Valid targets list in `/Layer1/valid_parameters.py` (`VALID_TARGETS` set)

## The Translation Gap

Layer 1 outputs species-level parameter changes:
```json
[
  {"target": "fishing_fleet.catch_rate", "operation": "multiply", "value": 0.35},
  {"target": "anchovy.mortality_rate", "operation": "multiply", "value": 0.75},
  {"target": "ocean.pollution_index", "operation": "multiply", "value": 0.8}
]
```

Layer 2 expects environment scalars:
```python
{
    "temperature": 16.2,
    "nutrients": 0.6,
    "pH": 8.05,
    "salinity": 33.4,
    "fishing_pressure": 0.2,
    "pollution_index": 0.3
}
```

The bridge converts between them.

## Translation Rules

| Layer 1 target pattern | Layer 2 environment key | Logic |
|---|---|---|
| `fishing_fleet.catch_rate` | `fishing_pressure` | Apply op directly |
| `fishing_fleet.effort_level` | `fishing_pressure` | Apply op directly (or avg if both present) |
| `<species>.mortality_rate` where species in {anchovy, sardine, sea_lion, leopard_shark, market_squid, pelican} | `fishing_pressure` (inverse) | Lower mortality implies lower fishing. If op=multiply value=0.75, then fishing_pressure *= 0.75 |
| `ocean.pollution_index` | `pollution_index` | Apply op directly |
| `coastal_community.runoff_rate` | `pollution_index` AND `nutrients` | Apply op to both |
| `ocean.temperature` | `temperature` | Apply op directly |
| `ocean.nutrient_level` | `nutrients` | Apply op directly |
| `ocean.ph` | `pH` | Apply op directly |
| `ocean.dissolved_oxygen` | no mapping | Skip |
| `<species>.reproduction_rate` | no mapping | Skip (Layer 2 handles via agent behavior) |
| `protected_area.coverage_percent` | `fishing_pressure` | op=set value=X → fishing_pressure = 0.2 * (1 - X/100) |

## Baseline & Clamping

```python
BASELINE_ENVIRONMENT = {
    "temperature": 16.2,
    "nutrients": 0.6,
    "pH": 8.05,
    "salinity": 33.4,
    "fishing_pressure": 0.2,
    "pollution_index": 0.3
}

CLAMP_RANGES = {
    "temperature": (10.0, 22.0),
    "nutrients": (0.0, 1.0),
    "pH": (7.8, 8.4),
    "salinity": (30.0, 36.0),
    "fishing_pressure": (0.0, 1.0),
    "pollution_index": (0.0, 1.0),
}
```

## File Layout to Create

```
integration/
├── INTEGRATION_CONTEXT.md     (this file)
├── layer2/                    (friend's species files, untouched)
├── bridge.py                  (translator)
├── orchestrator.py            (runs Layer 2 species per tick)
├── run_full_pipeline.py       (end-to-end runner)
└── tests/
    ├── __init__.py
    ├── test_bridge.py
    ├── test_orchestrator.py
    └── test_full_pipeline.py
```

## Build Steps — Execute in Order

### STEP 1 — Bridge (`bridge.py`)

Implement:
```python
def translate_to_environment(
    interpretation: PolicyInterpretation,
    baseline: Dict[str, float] = None
) -> Dict[str, float]
```

1. Start with baseline (or passed-in baseline).
2. For each `ParameterDelta` in `interpretation.parameter_deltas`:
   - Apply translation rule from table above
   - Use helper `_apply_op(current, op, value)` for multiply/add/set
3. Clamp all values to CLAMP_RANGES.
4. Return final environment dict.

Also implement `_apply_op(current, op, value) -> float`:
- multiply: current * value
- add: current + value
- set: value

**Tests (tests/test_bridge.py):**
- Trawling policy (fishing_fleet.catch_rate * 0.35) reduces fishing_pressure below baseline
- Pollution policy (ocean.pollution_index * 0.8) reduces pollution_index below baseline
- Empty parameter_deltas returns exact baseline
- Values clamp correctly (e.g., extreme multiply doesn't escape valid range)
- Unknown target is silently ignored (doesn't crash)

**Stop condition:** `pytest integration/tests/test_bridge.py -v` passes all tests.

### STEP 2 — Orchestrator (`orchestrator.py`)

Implement:
```python
def run_simulation(
    environment: Dict[str, float],
    num_ticks: int = 5,
    initial_state: Dict[str, Dict] = None
) -> List[Dict]
```

Import tick functions and agent states from each species file in layer2/.
Use `copy.deepcopy` on all module-level states before the loop — do NOT mutate the originals (running multiple simulations should be independent).

If `initial_state` is passed in, override specific species' starting states.

Execute tick order per tick (correct dependency order):
```python
for tick_num in range(1, num_ticks+1):
    phyto, phyto_behavior, phyto_reason = phyto_tick(phyto, environment)
    zoo, zoo_behavior, zoo_reason = zoo_tick(zoo, environment, phyto)
    anchovy, anchovy_behavior, anchovy_reason = anchovy_tick(anchovy, environment, zoo)
    sardine, sardine_behavior, sardine_reason = sardine_tick(sardine, environment, zoo, anchovy)
    sealion, sealion_behavior, sealion_reason = sealion_tick(sealion, environment, anchovy, sardine)
    # kelp/urchin pair: capture both pre-tick states before either updates
    kelp_prev = dict(kelp)
    urchin_prev = dict(urchin)
    kelp, kelp_behavior, kelp_reason = kelp_tick(kelp, environment, urchin_prev)
    urchin, urchin_behavior, urchin_reason = urchin_tick(urchin, environment, kelp_prev)
    snapshots.append(...)
```

Each snapshot:
```python
{
    "tick": tick_num,
    "species": {
        "phytoplankton": {**phyto, "behavior": phyto_behavior, "reason": phyto_reason},
        "zooplankton":   {**zoo,   "behavior": zoo_behavior,   "reason": zoo_reason},
        "anchovy":       {**anchovy, "behavior": anchovy_behavior, "reason": anchovy_reason},
        "sardine":       {**sardine, "behavior": sardine_behavior, "reason": sardine_reason},
        "sea_lion":      {**sealion, "behavior": sealion_behavior, "reason": sealion_reason},
        "kelp":          {**kelp,    "behavior": kelp_behavior,    "reason": kelp_reason},
        "urchin":        {**urchin,  "behavior": urchin_behavior,  "reason": urchin_reason},
    }
}
```

**Tests (tests/test_orchestrator.py):**
- Baseline environment produces 5 valid tick snapshots
- Each snapshot has all 7 species
- Populations stay in 0-100 range
- Running twice produces independent results (no global state mutation)

**Stop condition:** `pytest integration/tests/test_orchestrator.py -v` passes. Also: running orchestrator.py manually with baseline env produces 5 ticks with visible population changes (not all identical).

### STEP 3 — Full Pipeline (`run_full_pipeline.py`)

Implement:
```python
async def run_policy_simulation(
    policy_text: str,
    num_ticks: int = 5,
    region: str = "socal"
) -> Dict
```

1. Import from `Layer1.pipeline`: `interpret_policy`
2. Import from `Layer1.schema`: `PolicyRequest`
3. Build `PolicyRequest(policy_text=policy_text, region=region)`
4. Await `interpret_policy(request)` → get `PolicyInterpretation`
5. Call `bridge.translate_to_environment(interpretation)` → get env dict
6. Call `orchestrator.run_simulation(environment, num_ticks)` → get snapshots
7. Return:
```python
{
    "policy_interpretation": interpretation.model_dump(),
    "environment_after_policy": environment,
    "simulation_snapshots": snapshots,
    "num_ticks": num_ticks
}
```

**Tests (tests/test_full_pipeline.py):**
- Run with DEMO_MODE=true and canned trawling policy
- Assert environment.fishing_pressure < baseline (0.2)
- Assert 5 snapshots returned
- Assert snapshots contain all 7 species

**Stop condition:** Running `python run_full_pipeline.py` with "Ban commercial trawling" produces visible cascade (anchovy/sardine rising, sea_lion following).

### STEP 4 — FastAPI Endpoint

Add to `/Layer1/main.py`:
```python
from integration.run_full_pipeline import run_policy_simulation

@app.post("/simulate")
async def simulate(request: PolicyRequest, num_ticks: int = 5):
    return await run_policy_simulation(request.policy_text, num_ticks, request.region)
```

**Stop condition:** `curl POST /simulate` with trawling policy returns 200 with full payload including snapshots.

## Import Path Notes

Integration modules import from Layer 1. Ensure Python path is set so:
```python
from Layer1.schema import PolicyRequest, PolicyInterpretation
from Layer1.pipeline import interpret_policy
```
works. If needed, use `conftest.py` at `integration/tests/` or set `pythonpath` in pytest.ini.

Layer 2 species imports (inside orchestrator.py):
```python
from layer2.phytoplankton import tick as phyto_tick, agent as phyto_agent
from layer2.zooplankton import tick as zoo_tick, zooplankton as zoo_agent
from layer2.anchovy import tick as anchovy_tick, anchovy as anchovy_agent
from layer2.sardine import tick as sardine_tick, sardine as sardine_agent
from layer2.sealion import tick as sealion_tick, sea_lion as sealion_agent
from layer2.kelp import tick as kelp_tick, kelp as kelp_agent
from layer2.urchin import tick as urchin_tick, urchin as urchin_agent
```

## Environment Requirements

Integration needs BOTH keys in `.env`:
- `GEMINI_API_KEY` (for Layer 1)
- `GROQ_API_KEY` (for Layer 2)

If `GROQ_API_KEY` missing → orchestrator will crash on first tick. Fail loudly.

## Start Here

Begin with Step 1. Print a summary after each step. Wait for user confirmation before proceeding to the next step. Do not combine steps.
