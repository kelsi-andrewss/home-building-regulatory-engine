import json
import logging
import time
from dataclasses import dataclass

import anthropic

logger = logging.getLogger(__name__)

EXTRACTION_SYSTEM_PROMPT = """\
You are a zoning regulation analyst. Extract structured dimensional constraints \
and regulatory rules from the following LA City Specific Plan text.

For each rule you find, extract:
1. constraint_type: one of [setback_front, setback_side, setback_rear, height_max, \
far_max, density, lot_coverage, lot_area_min, lot_width_min, building_separation, \
open_space, landscaping, parking, use_restriction, design_standard, special_trigger]
2. value: numeric value (use the most restrictive if a range is given)
3. unit: one of [ft, stories, ratio, sf, percent, units_per_sf, spaces]
4. condition: any qualifying condition (e.g., "if lot > 10,000 sf", "for corner lots", \
"additions over 900 cumulative sf"). null if unconditional.
5. zone_applicability: which zones within this specific plan area the rule applies to. \
Use ["all"] if it applies to all zones in the plan area.
6. overrides_base_zone: true if this rule replaces the base zone rule, false if it \
supplements it.
7. override_behavior: "replace" if this completely replaces the base zone value, \
"most_restrictive" if the more restrictive of plan vs base zone applies. null if \
overrides_base_zone is false.
8. source_section: the section/article reference in the document.
9. source_page: the page number this rule appears on.
10. extraction_reasoning: 1-2 sentences explaining why you interpreted the text as \
this specific constraint. Quote the key phrase from the source.

Focus on:
- Dimensional constraints (setbacks, height limits, FAR, lot coverage, density)
- Use restrictions (permitted, conditional, prohibited uses)
- Design standards (materials, articulation, roof pitch, fenestration)
- Special triggers (thresholds that activate additional review or requirements)
- Override behavior: does this plan REPLACE the base zone rule, or does \
"whichever is more restrictive" apply?

If a rule is ambiguous, extract it with your best interpretation and explain \
the ambiguity in extraction_reasoning.

Respond with a JSON array of objects matching the schema above. No other text."""

RETRY_MESSAGE = "Your previous response was not valid JSON. Please return ONLY a valid JSON array of objects matching the schema. No other text."

# Transient error status codes that warrant retry
TRANSIENT_STATUS_CODES = {429, 500, 529}


@dataclass
class ExtractedFragment:
    """Raw extraction result before DB insertion."""
    constraint_type: str
    value: float | None
    unit: str
    condition: str | None
    zone_applicability: list[str]
    overrides_base_zone: bool
    override_behavior: str | None
    source_section: str
    source_page: int
    extraction_reasoning: str


class ClaudeClient:
    """Claude API client for structuring regulatory text into rule fragments."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def extract_rule_fragments(
        self,
        text_chunk: str,
        document_name: str,
        document_url: str,
    ) -> list[ExtractedFragment]:
        """Send regulatory text to Claude with structured extraction prompt.
        Returns list of ExtractedFragment objects parsed from Claude's response.
        Retries up to 3 times on transient API errors."""
        user_message = (
            f"Document: {document_name}\n"
            f"URL: {document_url}\n\n"
            f"---\n{text_chunk}\n---\n\n"
            f"Extract all regulatory constraints from this text as JSON."
        )

        response_text = self._call_with_retry(user_message, max_retries=3)
        return self._parse_response(response_text, document_name)

    def _call_with_retry(self, user_message: str, max_retries: int = 3) -> str:
        last_error = None
        for attempt in range(max_retries):
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    system=EXTRACTION_SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": user_message}],
                )
                return response.content[0].text
            except anthropic.APIStatusError as e:
                if e.status_code in TRANSIENT_STATUS_CODES and attempt < max_retries - 1:
                    logger.warning(
                        "Transient API error (status %d), attempt %d/%d",
                        e.status_code, attempt + 1, max_retries,
                    )
                    last_error = e
                    time.sleep(2 ** attempt)
                    continue
                raise
            except anthropic.APIConnectionError as e:
                if attempt < max_retries - 1:
                    logger.warning(
                        "API connection error, attempt %d/%d",
                        attempt + 1, max_retries,
                    )
                    last_error = e
                    time.sleep(2 ** attempt)
                    continue
                raise

        raise last_error  # type: ignore[misc]

    def _parse_response(
        self, response_text: str, document_name: str
    ) -> list[ExtractedFragment]:
        # Try to parse the JSON response
        try:
            fragments_raw = self._extract_json(response_text)
        except (json.JSONDecodeError, ValueError):
            # Retry once with a nudge for valid JSON
            logger.warning(
                "Malformed JSON from Claude for %s, retrying with nudge",
                document_name,
            )
            try:
                retry_response = self.client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    system=EXTRACTION_SYSTEM_PROMPT,
                    messages=[
                        {"role": "user", "content": response_text},
                        {"role": "assistant", "content": response_text},
                        {"role": "user", "content": RETRY_MESSAGE},
                    ],
                )
                fragments_raw = self._extract_json(retry_response.content[0].text)
            except (json.JSONDecodeError, ValueError, anthropic.APIError) as e:
                logger.error(
                    "Failed to parse JSON from Claude for %s after retry: %s",
                    document_name, e,
                )
                return []

        return [self._to_fragment(raw) for raw in fragments_raw]

    def _extract_json(self, text: str) -> list[dict]:
        """Extract JSON array from response text, handling markdown fences."""
        text = text.strip()
        if text.startswith("```"):
            # Strip markdown code fences
            lines = text.split("\n")
            # Remove first and last lines (fences)
            lines = [l for l in lines[1:] if not l.strip().startswith("```")]
            text = "\n".join(lines)

        result = json.loads(text)
        if not isinstance(result, list):
            raise ValueError("Expected JSON array")
        return result

    def _to_fragment(self, raw: dict) -> ExtractedFragment:
        return ExtractedFragment(
            constraint_type=raw.get("constraint_type", "unknown"),
            value=raw.get("value"),
            unit=raw.get("unit", ""),
            condition=raw.get("condition"),
            zone_applicability=raw.get("zone_applicability", ["all"]),
            overrides_base_zone=raw.get("overrides_base_zone", False),
            override_behavior=raw.get("override_behavior"),
            source_section=raw.get("source_section", ""),
            source_page=raw.get("source_page", 0),
            extraction_reasoning=raw.get("extraction_reasoning", ""),
        )
