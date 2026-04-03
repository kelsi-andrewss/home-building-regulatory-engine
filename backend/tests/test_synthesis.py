import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.prompts.synthesis import build_user_prompt
from backend.app.services.synthesis_service import (
    MODEL,
    FALLBACK_SUMMARY,
    SynthesisService,
)

SAMPLE_PARCEL = {
    "apn": "5432-001-001",
    "address": "123 Test St, Los Angeles, CA 90001",
    "zone_complete": "R1-1",
    "zone_class": "R1",
    "height_district": "1",
    "lot_area_sf": 7500,
}

SAMPLE_CONSTRAINTS = [
    {
        "constraint_type": "height_max",
        "value": 33,
        "unit": "ft",
        "confidence": "verified",
        "citation": "LAMC SS12.08",
        "overrides_base_zone": False,
    },
    {
        "constraint_type": "setback_front",
        "value": 20,
        "unit": "ft",
        "confidence": "verified",
        "citation": "LAMC SS12.08",
        "overrides_base_zone": False,
    },
]

VALID_CLAUDE_RESPONSE = {
    "summary": "This R1-1 parcel at 123 Test St permits a single-family dwelling with a maximum height of 33 ft (LAMC SS12.08) and 20 ft front setback.",
    "constraint_explanations": [
        {
            "constraint_name": "Max Height",
            "value": "33 ft",
            "confidence": "verified",
            "explanation": "Per LAMC SS12.08, R1 zones have a 33 ft height limit.",
            "citation": {"document": "LAMC SS12.08", "section": None, "page": None},
            "overrides_base_zone": False,
        },
        {
            "constraint_name": "Front Setback",
            "value": "20 ft",
            "confidence": "verified",
            "explanation": "Per LAMC SS12.08, R1 zones require a 20 ft front yard setback.",
            "citation": {"document": "LAMC SS12.08", "section": None, "page": None},
            "overrides_base_zone": False,
        },
    ],
    "override_highlights": [],
    "adu_opportunities": [],
}

OVERRIDE_CLAUDE_RESPONSE = {
    "summary": "This parcel is subject to the Mulholland Scenic Parkway Specific Plan, which reduces the max height to 24 ft.",
    "constraint_explanations": [
        {
            "constraint_name": "Max Height",
            "value": "24 ft",
            "confidence": "interpreted",
            "explanation": "Mulholland Scenic Parkway Specific Plan Section 7.B limits height to 24 ft, overriding the base R1 zone 33 ft limit.",
            "citation": {
                "document": "Mulholland Scenic Parkway Specific Plan",
                "section": "Section 7.B",
                "page": 12,
            },
            "overrides_base_zone": True,
        },
    ],
    "override_highlights": [
        "Mulholland Scenic Parkway Specific Plan overrides Max Height: 24 ft (more restrictive than base zone 33 ft)"
    ],
    "adu_opportunities": [
        {
            "description": "Owner may build one ADU up to 1,200 sf per CA Gov. Code SS65852.2, regardless of specific plan restrictions.",
            "citations": [
                {"document": "CA Gov. Code SS65852.2", "section": None, "page": None}
            ],
            "guaranteed_by_state_law": True,
        }
    ],
}


def _mock_client(response_text: str) -> MagicMock:
    client = MagicMock()
    message = MagicMock()
    message.content = [MagicMock(text=response_text)]
    client.messages.create = AsyncMock(return_value=message)
    return client


class TestBuildUserPrompt:
    def test_formats_correctly(self):
        prompt = build_user_prompt(
            SAMPLE_PARCEL, SAMPLE_CONSTRAINTS, "Mulholland Scenic Parkway", ["HPOZ"]
        )
        assert "5432-001-001" in prompt
        assert "123 Test St" in prompt
        assert "R1-1" in prompt
        assert "R1" in prompt
        assert "height_max" in prompt
        assert "Mulholland Scenic Parkway" in prompt
        assert "HPOZ" in prompt

    def test_handles_no_specific_plan(self):
        prompt = build_user_prompt(SAMPLE_PARCEL, SAMPLE_CONSTRAINTS, None, [])
        assert "Specific plan: None" in prompt
        assert "Overlays: None" in prompt

    def test_constraints_json_serialized(self):
        prompt = build_user_prompt(SAMPLE_PARCEL, SAMPLE_CONSTRAINTS, None, [])
        # The constraints JSON should be parseable within the prompt
        assert '"constraint_type": "height_max"' in prompt
        assert '"value": 33' in prompt


class TestSynthesizeValidResponse:
    @pytest.mark.asyncio
    async def test_parses_valid_response(self):
        client = _mock_client(json.dumps(VALID_CLAUDE_RESPONSE))
        service = SynthesisService(client)

        result = await service.synthesize(
            SAMPLE_PARCEL, SAMPLE_CONSTRAINTS, None, []
        )

        assert result.summary == VALID_CLAUDE_RESPONSE["summary"]
        assert len(result.constraint_explanations) == 2
        assert result.constraint_explanations[0].constraint_name == "Max Height"
        assert result.constraint_explanations[0].value == "33 ft"
        assert result.constraint_explanations[0].confidence == "verified"
        assert result.constraint_explanations[0].citation.document == "LAMC SS12.08"
        assert result.constraint_explanations[0].overrides_base_zone is False
        assert result.model_used == MODEL
        assert result.override_highlights == []
        assert result.adu_opportunities == []

    @pytest.mark.asyncio
    async def test_calls_claude_with_correct_params(self):
        client = _mock_client(json.dumps(VALID_CLAUDE_RESPONSE))
        service = SynthesisService(client)

        await service.synthesize(SAMPLE_PARCEL, SAMPLE_CONSTRAINTS, None, [])

        call_kwargs = client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == MODEL
        assert call_kwargs["temperature"] == 0
        assert call_kwargs["max_tokens"] == 2048
        assert "zoning regulatory analyst" in call_kwargs["system"]
        assert "5432-001-001" in call_kwargs["messages"][0]["content"]


class TestSynthesizeMalformedResponse:
    @pytest.mark.asyncio
    async def test_handles_non_json(self):
        client = _mock_client("I cannot produce valid JSON right now.")
        service = SynthesisService(client)

        result = await service.synthesize(
            SAMPLE_PARCEL, SAMPLE_CONSTRAINTS, None, []
        )

        assert result.summary == FALLBACK_SUMMARY
        assert result.constraint_explanations == []
        assert result.override_highlights == []
        assert result.adu_opportunities == []
        assert result.model_used == MODEL

    @pytest.mark.asyncio
    async def test_handles_missing_keys(self):
        # JSON but missing required "summary" key
        client = _mock_client(json.dumps({"constraint_explanations": []}))
        service = SynthesisService(client)

        result = await service.synthesize(
            SAMPLE_PARCEL, SAMPLE_CONSTRAINTS, None, []
        )

        assert result.summary == FALLBACK_SUMMARY
        assert result.constraint_explanations == []


class TestOverrideHighlights:
    @pytest.mark.asyncio
    async def test_override_highlights_populated(self):
        client = _mock_client(json.dumps(OVERRIDE_CLAUDE_RESPONSE))
        service = SynthesisService(client)

        result = await service.synthesize(
            SAMPLE_PARCEL, SAMPLE_CONSTRAINTS, "Mulholland Scenic Parkway", ["HPOZ"]
        )

        assert len(result.override_highlights) == 1
        assert "Mulholland Scenic Parkway" in result.override_highlights[0]
        assert "more restrictive" in result.override_highlights[0]

        assert len(result.constraint_explanations) == 1
        assert result.constraint_explanations[0].overrides_base_zone is True
        assert result.constraint_explanations[0].citation.section == "Section 7.B"
        assert result.constraint_explanations[0].citation.page == 12

        assert len(result.adu_opportunities) == 1
        assert result.adu_opportunities[0].guaranteed_by_state_law is True
        assert "Gov. Code" in result.adu_opportunities[0].citations[0].document
