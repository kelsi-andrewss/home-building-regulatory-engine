from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

import anthropic

from backend.app.prompts.synthesis import SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-20250514"
FALLBACK_SUMMARY = (
    "Synthesis unavailable — constraint data returned without natural language summary."
)


@dataclass
class Citation:
    document: str
    section: str | None = None
    page: int | None = None


@dataclass
class ConstraintExplanation:
    constraint_name: str
    value: str
    confidence: str
    explanation: str
    citation: Citation
    overrides_base_zone: bool


@dataclass
class ADUOpportunity:
    description: str
    citations: list[Citation]
    guaranteed_by_state_law: bool


@dataclass
class SynthesisResult:
    summary: str
    constraint_explanations: list[ConstraintExplanation]
    override_highlights: list[str]
    adu_opportunities: list[ADUOpportunity]
    model_used: str


def _degraded_result() -> SynthesisResult:
    return SynthesisResult(
        summary=FALLBACK_SUMMARY,
        constraint_explanations=[],
        override_highlights=[],
        adu_opportunities=[],
        model_used=MODEL,
    )


def _parse_citation(raw: dict) -> Citation:
    return Citation(
        document=raw.get("document", ""),
        section=raw.get("section"),
        page=raw.get("page"),
    )


def _parse_constraint_explanation(raw: dict) -> ConstraintExplanation:
    return ConstraintExplanation(
        constraint_name=raw["constraint_name"],
        value=raw["value"],
        confidence=raw["confidence"],
        explanation=raw["explanation"],
        citation=_parse_citation(raw.get("citation", {})),
        overrides_base_zone=raw.get("overrides_base_zone", False),
    )


def _parse_adu_opportunity(raw: dict) -> ADUOpportunity:
    return ADUOpportunity(
        description=raw["description"],
        citations=[_parse_citation(c) for c in raw.get("citations", [])],
        guaranteed_by_state_law=raw.get("guaranteed_by_state_law", False),
    )


def _strip_markdown_fences(text: str) -> str:
    """Remove ```json / ``` wrappers that LLMs sometimes add around JSON."""
    return re.sub(r"^```\w*\n?", "", text).rstrip("`").strip()


class SynthesisService:
    """Translates resolved rule engine constraints into cited natural language."""

    def __init__(self, anthropic_client):
        self.client = anthropic_client

    async def synthesize(
        self,
        parcel: dict,
        constraints: list[dict],
        specific_plan: str | None,
        overlays: list[str],
    ) -> SynthesisResult:
        user_prompt = build_user_prompt(parcel, constraints, specific_plan, overlays)

        try:
            response = await self.client.messages.create(
                model=MODEL,
                max_tokens=2048,
                temperature=0,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
            response_text = response.content[0].text
        except (anthropic.APIError, anthropic.APIConnectionError):
            logger.exception("Claude API call failed during synthesis")
            return _degraded_result()

        try:
            data = json.loads(_strip_markdown_fences(response_text))
        except json.JSONDecodeError:
            logger.warning("Malformed JSON from Claude synthesis response")
            return _degraded_result()

        try:
            return SynthesisResult(
                summary=data["summary"],
                constraint_explanations=[
                    _parse_constraint_explanation(ce)
                    for ce in data.get("constraint_explanations", [])
                ],
                override_highlights=data.get("override_highlights", []),
                adu_opportunities=[
                    _parse_adu_opportunity(adu)
                    for adu in data.get("adu_opportunities", [])
                ],
                model_used=MODEL,
            )
        except (KeyError, TypeError):
            logger.warning("Unexpected structure in Claude synthesis response")
            return _degraded_result()
