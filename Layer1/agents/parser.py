"""Parser agent: natural-language policy → structured ParsedIntent (Gemini JSON)."""

from __future__ import annotations

import json
import logging
from typing import Any

from google.genai import errors as genai_errors
from pydantic import BaseModel, Field, ValidationError

from llm import chat_json

logger = logging.getLogger(__name__)


class ParsedIntent(BaseModel):
    """Structured intent extracted from free-text policy language."""

    action_type: str = Field(
        ...,
        description="High-level policy verb, e.g. ban, restrict, establish, increase, regulate, unclear.",
    )
    target_activity: str = Field(
        ...,
        description="Primary activity or object being regulated (e.g. commercial_trawling, mpa, runoff).",
    )
    scope_geographic: str = Field(
        ...,
        description="Where the policy applies (region, distance from shore, jurisdiction).",
    )
    scope_temporal: str = Field(
        ...,
        description="Duration or phase: permanent, seasonal, multi-year, immediate, unspecified.",
    )
    magnitude: str = Field(
        ...,
        description="Strength, caps, or extent (percent, distance, tonnage) or 'unspecified'.",
    )
    affected_species: list[str] = Field(
        default_factory=list,
        description="Species or groups explicitly or reasonably implied; empty if none.",
    )


def _parser_prompt(policy_text: str) -> str:
    """Build the full user prompt with instructions and few-shot JSON examples."""
    schema_hint = (
        "Return a single JSON object with exactly these keys (all string values except "
        "affected_species which is an array of strings): "
        "action_type, target_activity, scope_geographic, scope_temporal, magnitude, affected_species. "
        "Use lowercase snake_case for action_type and target_activity where helpful. "
        "If the policy is vague, set action_type to 'unclear' and explain uncertainty in magnitude "
        "or scope fields with plain language."
    )
    few_shots = """
Few-shot example 1 (input → output JSON):
INPUT: Ban commercial bottom trawling within 50 miles of the California coast for five years.
OUTPUT:
{"action_type":"ban","target_activity":"commercial_bottom_trawling","scope_geographic":"within 50 miles of California coast","scope_temporal":"five years","magnitude":"100 percent prohibition inside zone","affected_species":["groundfish","benthic invertebrates","commercial target fish"]}

Few-shot example 2 (input → output JSON):
INPUT: Establish a no-take marine protected area covering 12% of Southern California state waters.
OUTPUT:
{"action_type":"establish","target_activity":"marine_protected_area","scope_geographic":"Southern California state waters","scope_temporal":"unspecified duration in text","magnitude":"12 percent area no-take","affected_species":["rockfish","kelp forest species","sea lions"]}

Few-shot example 3 (input → output JSON):
INPUT: Require farms in coastal watersheds to cut fertilizer use by 30% to reduce algal blooms.
OUTPUT:
{"action_type":"regulate","target_activity":"agricultural_runoff","scope_geographic":"coastal watersheds","scope_temporal":"ongoing compliance","magnitude":"30 percent reduction in fertilizer use","affected_species":["phytoplankton","zooplankton","fish larvae"]}
"""
    return (
        "You are a marine and coastal sustainability policy parser for the US West Coast context.\n"
        f"{schema_hint}\n"
        f"{few_shots}\n"
        "Now parse the following policy. Respond with ONLY the JSON object, no markdown fences.\n\n"
        f"INPUT: {policy_text.strip()}\n"
        "OUTPUT:"
    )


_FALLBACK_INTENT_SHAPE = ParsedIntent(
    action_type="unclear",
    target_activity="unspecified",
    scope_geographic="unspecified",
    scope_temporal="unspecified",
    magnitude="unspecified",
    affected_species=[],
)


def _fallback_intent(policy_text: str, reason: str) -> ParsedIntent:
    logger.warning("parse_policy: using fallback intent (%s)", reason)
    return _FALLBACK_INTENT_SHAPE.model_copy(deep=True)


def is_api_fallback_intent(parsed: ParsedIntent) -> bool:
    """True when ``parse_policy`` substituted the conservative default (e.g. API/quota failure)."""
    return parsed.model_dump() == _FALLBACK_INTENT_SHAPE.model_dump()


def parse_policy(policy_text: str) -> ParsedIntent:
    """
    Parse free-text policy into structured fields using Gemini JSON mode.

    Input:
        policy_text — raw user policy string (any length).

    Output:
        ParsedIntent — validated structured intent.

    Failure modes:
        JSON decode errors are retried once inside ``chat_json`` with a stricter tail prompt.
        Gemini ``APIError`` (rate limits, outages) returns the same conservative fallback intent.
        If Pydantic validation fails after one additional structured retry, returns that fallback.
        ``RuntimeError`` from a missing API key is not caught and propagates.
    """
    stripped = policy_text.strip()
    if not stripped:
        return _fallback_intent(policy_text, "empty policy text")

    base_prompt = _parser_prompt(stripped)

    def _validate(data: dict[str, Any]) -> ParsedIntent:
        return ParsedIntent.model_validate(data)

    try:
        data = chat_json(base_prompt)
        return _validate(data)
    except genai_errors.APIError as err:
        logger.warning("parse_policy: Gemini API error, using fallback: %s", err)
        return _fallback_intent(stripped, "gemini api")
    except json.JSONDecodeError as err:
        logger.warning("parse_policy: JSON failure after llm retries: %s", err)
        return _fallback_intent(stripped, "json decode")
    except ValidationError as err:
        logger.warning("parse_policy: validation failed, retrying with errors: %s", err)
        retry_prompt = (
            f"{base_prompt}\n\n"
            "Your previous JSON failed schema validation. Fix it. Required shape: "
            '{"action_type": string, "target_activity": string, "scope_geographic": string, '
            '"scope_temporal": string, "magnitude": string, "affected_species": [strings...]}. '
            "Return ONLY valid JSON, no markdown."
        )
        try:
            data2 = chat_json(retry_prompt)
            return _validate(data2)
        except genai_errors.APIError as err_api:
            logger.warning("parse_policy: API error on validation retry: %s", err_api)
            return _fallback_intent(stripped, "gemini api on retry")
        except (json.JSONDecodeError, ValidationError) as err2:
            logger.warning("parse_policy: retry failed: %s", err2)
            return _fallback_intent(stripped, "validation after retry")
