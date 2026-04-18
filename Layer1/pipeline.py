"""Policy interpretation orchestration (parser live; downstream agents still stubbed)."""

from __future__ import annotations

from agents.parser import ParsedIntent, parse_policy
from schema import ParameterDelta, PolicyInterpretation, PolicyRequest, Source


def interpret_policy(request: PolicyRequest) -> PolicyInterpretation:
    """
    Interpret a policy: parse with Gemini, then return a stub interpretation (Steps 4–6 pending).

    Input:
        request — user policy text and optional region.

    Output:
        PolicyInterpretation — schema-valid; parameter deltas still illustrative.

    Failure modes:
        Parser falls back to an ``unclear`` intent on empty input or repeated validation failure;
        missing ``GEMINI_API_KEY`` raises when parsing is attempted.
    """
    parsed: ParsedIntent = parse_policy(request.policy_text)
    species_preview = (
        ", ".join(parsed.affected_species[:5])
        if parsed.affected_species
        else "(none named)"
    )
    reasoning_trace = [
        f"Received policy text for region {request.region!r}.",
        (
            f"Parser: action_type={parsed.action_type!r}, "
            f"target_activity={parsed.target_activity!r}, "
            f"scope_geographic={parsed.scope_geographic!r}."
        ),
        (
            f"Parser: scope_temporal={parsed.scope_temporal!r}, magnitude={parsed.magnitude!r}, "
            f"affected_species={species_preview}."
        ),
        "Research agents not wired — skipping literature, history, and datasets.",
        "Synthesizer not wired — emitting a single illustrative parameter delta.",
    ]
    return PolicyInterpretation(
        plain_english_summary=(
            f"Parsed intent: {parsed.action_type} affecting {parsed.target_activity} "
            f"({parsed.scope_geographic}). Downstream synthesis is still stubbed; "
            "anchovy mortality multiplier shown as a placeholder ecological lever."
        ),
        parameter_deltas=[
            ParameterDelta(
                target="anchovy.mortality_rate",
                operation="multiply",
                value=0.6,
                rationale=(
                    "Illustrative delta pending full pipeline: reduced fishing pressure "
                    f"often lowers forage-fish mortality under policies like {parsed.action_type!r}."
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
        reasoning_trace=reasoning_trace,
        warnings=[
            "Research, skeptic, and synthesizer agents not yet wired — "
            "parameter deltas are placeholders only."
        ],
    )
