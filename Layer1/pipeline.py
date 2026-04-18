"""Policy interpretation orchestration (stub: mock output until agents are wired)."""

from __future__ import annotations

from schema import ParameterDelta, PolicyInterpretation, PolicyRequest, Source


def interpret_policy(request: PolicyRequest) -> PolicyInterpretation:
    """
    Return a valid interpretation with hardcoded values for integration testing.

    Input:
        request — user policy text and optional region.

    Output:
        PolicyInterpretation — always schema-valid in Step 2.

    Failure modes:
        None for the stub; later steps handle LLM and validation failures.
    """
    _ = request  # Stub ignores input; real pipeline will use policy_text.
    return PolicyInterpretation(
        plain_english_summary=(
            "Stub response: a hypothetical coastal fishing restriction would "
            "reduce direct mortality on small pelagic forage fish while "
            "ecosystem effects propagate through plankton and predators."
        ),
        parameter_deltas=[
            ParameterDelta(
                target="anchovy.mortality_rate",
                operation="multiply",
                value=0.6,
                rationale=(
                    "Lower fishing-related mortality multiplier under a "
                    "commercial pressure reduction scenario (illustrative)."
                ),
            )
        ],
        confidence=0.75,
        sources=[
            Source(
                title="CalCOFI and fisheries reference (mock)",
                url="https://example.org/calcofi-mock",
                excerpt=(
                    "Illustrative excerpt: time series show covariability of "
                    "forage fish biomass with fishing effort in the CCS."
                ),
            )
        ],
        reasoning_trace=[
            "Received policy text and region for interpretation (stub).",
            "Parser agent not wired — using placeholder structured intent.",
            "Research agents not wired — skipping literature, history, and datasets.",
            "Synthesizer not wired — emitting a single validated parameter delta for demo.",
        ],
        warnings=["Stub pipeline: replace with live agents in later steps."],
    )
