"""End-to-end PDF ingestion tests.

Feeds real PDF fixtures through PdfProcessor (real pdfplumber extraction),
with only the Anthropic API call mocked. Tests the full chain:
PDF parsing -> chunking -> response parsing -> validation -> storage.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.clients.claude_client import ClaudeClient, ExtractedFragment
from backend.app.services.ingestion_pipeline import IngestionPipeline, IngestionStatus
from backend.app.services.pdf_processor import PdfExtractionError, PdfProcessor


# ---------------------------------------------------------------------------
# Canned Claude JSON responses matching fixture content
# ---------------------------------------------------------------------------

HEIGHT_SETBACK_CLAUDE_RESPONSE = json.dumps([
    {
        "constraint_type": "height_max",
        "value": 33,
        "unit": "ft",
        "condition": None,
        "zone_applicability": ["all"],
        "overrides_base_zone": True,
        "override_behavior": "replace",
        "source_section": "Section 7.B",
        "source_page": 1,
        "extraction_reasoning": "Section 7.B states 'No building or structure shall exceed 33 feet or 2 stories in height'.",
    },
    {
        "constraint_type": "setback_front",
        "value": 15,
        "unit": "ft",
        "condition": None,
        "zone_applicability": ["all"],
        "overrides_base_zone": False,
        "override_behavior": "most_restrictive",
        "source_section": "Section 9.A",
        "source_page": 1,
        "extraction_reasoning": "Section 9.A specifies 'Front yard setback: 15 feet minimum'.",
    },
    {
        "constraint_type": "setback_side",
        "value": 5,
        "unit": "ft",
        "condition": "for interior lots",
        "zone_applicability": ["all"],
        "overrides_base_zone": False,
        "override_behavior": "most_restrictive",
        "source_section": "Section 9.A",
        "source_page": 1,
        "extraction_reasoning": "Section 9.A specifies 'Side yard setback: 5 feet minimum for interior lots'.",
    },
    {
        "constraint_type": "setback_rear",
        "value": 15,
        "unit": "ft",
        "condition": None,
        "zone_applicability": ["all"],
        "overrides_base_zone": False,
        "override_behavior": "most_restrictive",
        "source_section": "Section 9.A",
        "source_page": 1,
        "extraction_reasoning": "Section 9.A specifies 'Rear yard setback: 15 feet'.",
    },
])

OUTLIER_CLAUDE_RESPONSE = json.dumps([
    {
        "constraint_type": "height_max",
        "value": 500,
        "unit": "ft",
        "condition": None,
        "zone_applicability": ["all"],
        "overrides_base_zone": True,
        "override_behavior": "replace",
        "source_section": "Section 7.B",
        "source_page": 1,
        "extraction_reasoning": "Misread height as 500 feet.",
    },
    {
        "constraint_type": "setback_front",
        "value": 15,
        "unit": "ft",
        "condition": None,
        "zone_applicability": ["all"],
        "overrides_base_zone": False,
        "override_behavior": "most_restrictive",
        "source_section": "Section 9.A",
        "source_page": 1,
        "extraction_reasoning": "Front setback 15 feet.",
    },
])

DESIGN_STANDARDS_CLAUDE_RESPONSE = json.dumps([
    {
        "constraint_type": "design_standard",
        "value": None,
        "unit": "",
        "condition": None,
        "zone_applicability": ["all"],
        "overrides_base_zone": True,
        "override_behavior": "replace",
        "source_section": "Section 12.A",
        "source_page": 1,
        "extraction_reasoning": "Section 12.A specifies 'Exterior materials shall be limited to stucco, wood siding, or stone veneer'.",
        "design_standards": [
            {
                "category": "material",
                "requirement_text": "Exterior materials shall be limited to stucco, wood siding, or stone veneer on all street-facing facades",
                "allowed_values": ["stucco", "wood siding", "stone veneer"],
                "numeric_value": None,
                "numeric_unit": None,
                "applies_to": "street-facing",
            },
        ],
    },
    {
        "constraint_type": "design_standard",
        "value": None,
        "unit": "",
        "condition": None,
        "zone_applicability": ["all"],
        "overrides_base_zone": True,
        "override_behavior": "replace",
        "source_section": "Section 12.C",
        "source_page": 1,
        "extraction_reasoning": "Section 12.C requires 'Building articulation required every 30 feet of continuous wall length'.",
        "design_standards": [
            {
                "category": "articulation",
                "requirement_text": "Building articulation required every 30 feet of continuous wall length",
                "allowed_values": None,
                "numeric_value": 30,
                "numeric_unit": "ft",
                "applies_to": "street-facing",
            },
        ],
    },
])

EMPTY_CLAUDE_RESPONSE = json.dumps([])

MARKDOWN_FENCED_RESPONSE = f"```json\n{HEIGHT_SETBACK_CLAUDE_RESPONSE}\n```"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_claude_response(canned_json: str) -> MagicMock:
    """Create a mock anthropic messages.create response returning canned JSON."""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=canned_json)]
    return mock_response


def _mock_db_session() -> AsyncMock:
    """Create an AsyncMock DB session that accepts adds/flushes/commits."""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    )
    return session


# ---------------------------------------------------------------------------
# TestPdfExtractionE2E: real pdfplumber, no Claude
# ---------------------------------------------------------------------------

class TestPdfExtractionE2E:
    def test_extract_height_setback_fixture(self, height_setback_pdf: Path):
        processor = PdfProcessor(cache_dir="/tmp/test_pdfs_e2e")
        doc = processor.extract_from_path(height_setback_pdf)

        assert doc.total_pages >= 1
        full_text = " ".join(p.text for p in doc.pages)
        assert "33 feet" in full_text
        assert "15 feet" in full_text
        assert "etback" in full_text  # "Setback" or "setback"

    def test_extract_design_standards_fixture(self, design_standards_pdf: Path):
        processor = PdfProcessor(cache_dir="/tmp/test_pdfs_e2e")
        doc = processor.extract_from_path(design_standards_pdf)

        assert doc.total_pages >= 1
        full_text = " ".join(p.text for p in doc.pages)
        assert "stucco" in full_text
        assert "articulation" in full_text.lower()
        assert "4:12" in full_text

    def test_malformed_pdf_raises(self, malformed_pdf: Path):
        processor = PdfProcessor(cache_dir="/tmp/test_pdfs_e2e")
        with pytest.raises(PdfExtractionError):
            processor.extract_from_path(malformed_pdf)

    def test_chunking_preserves_all_text(self, height_setback_pdf: Path):
        processor = PdfProcessor(cache_dir="/tmp/test_pdfs_e2e")
        doc = processor.extract_from_path(height_setback_pdf)
        chunks = processor.chunk_document(doc)

        assert len(chunks) >= 1
        all_chunk_text = " ".join(chunks)
        assert "33 feet" in all_chunk_text
        assert "15 feet" in all_chunk_text
        for chunk in chunks:
            assert chunk.startswith("[Pages ")


# ---------------------------------------------------------------------------
# TestIngestionPipelineE2E: real PDF + canned Claude + real validation + mock DB
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestIngestionPipelineE2E:

    async def test_full_pipeline_height_setback(self, height_setback_pdf: Path):
        """Real PDF -> canned Claude response -> all 4 fragments extracted, none flagged."""
        processor = PdfProcessor(cache_dir="/tmp/test_pdfs_e2e")
        doc = processor.extract_from_path(height_setback_pdf)
        chunks = processor.chunk_document(doc)
        assert len(chunks) >= 1

        client = ClaudeClient(api_key="test-key")
        mock_resp = _mock_claude_response(HEIGHT_SETBACK_CLAUDE_RESPONSE)
        session = _mock_db_session()

        pipeline = IngestionPipeline(
            pdf_processor=processor,
            claude_client=client,
            db_session=session,
        )

        all_fragments: list[ExtractedFragment] = []
        with patch.object(client.client.messages, "create", return_value=mock_resp):
            for chunk in chunks:
                fragments = client.extract_rule_fragments(
                    text_chunk=chunk,
                    document_name="Silver Lake SP",
                    document_url="http://example.com/slsp.pdf",
                )
                all_fragments.extend(fragments)

        assert len(all_fragments) == 4

        expected_types = {"height_max", "setback_front", "setback_side", "setback_rear"}
        actual_types = {f.constraint_type for f in all_fragments}
        assert actual_types == expected_types

        # All values within validation ranges -- none flagged
        for fragment in all_fragments:
            warnings = pipeline.validate_fragment(fragment)
            assert warnings == [], f"{fragment.constraint_type}={fragment.value} flagged: {warnings}"

        # Verify specific values
        by_type = {f.constraint_type: f for f in all_fragments}
        assert by_type["height_max"].value == 33
        assert by_type["setback_front"].value == 15
        assert by_type["setback_side"].value == 5
        assert by_type["setback_side"].condition == "for interior lots"
        assert by_type["setback_rear"].value == 15

    async def test_full_pipeline_flags_outlier(self, height_setback_pdf: Path):
        """Canned response with height_max=500 -> flagged with validation warning."""
        processor = PdfProcessor(cache_dir="/tmp/test_pdfs_e2e")
        doc = processor.extract_from_path(height_setback_pdf)
        chunks = processor.chunk_document(doc)

        client = ClaudeClient(api_key="test-key")
        mock_resp = _mock_claude_response(OUTLIER_CLAUDE_RESPONSE)
        session = _mock_db_session()

        pipeline = IngestionPipeline(
            pdf_processor=processor,
            claude_client=client,
            db_session=session,
        )

        all_fragments: list[ExtractedFragment] = []
        with patch.object(client.client.messages, "create", return_value=mock_resp):
            for chunk in chunks:
                fragments = client.extract_rule_fragments(
                    text_chunk=chunk,
                    document_name="Silver Lake SP",
                    document_url="http://example.com/slsp.pdf",
                )
                all_fragments.extend(fragments)

        assert len(all_fragments) == 2

        outlier = [f for f in all_fragments if f.constraint_type == "height_max"][0]
        assert outlier.value == 500
        warnings = pipeline.validate_fragment(outlier)
        assert len(warnings) == 1
        assert "above maximum" in warnings[0]

        # Simulate what ingest_document does: append warning to reasoning
        outlier.extraction_reasoning = (
            f"{outlier.extraction_reasoning} [VALIDATION WARNING: {'; '.join(warnings)}]"
        )
        assert "[VALIDATION WARNING:" in outlier.extraction_reasoning

        # The valid fragment should pass
        valid = [f for f in all_fragments if f.constraint_type == "setback_front"][0]
        assert pipeline.validate_fragment(valid) == []

    async def test_pipeline_handles_empty_claude_response(self, height_setback_pdf: Path):
        """Empty array from Claude -> 0 fragments, status COMPLETED."""
        processor = PdfProcessor(cache_dir="/tmp/test_pdfs_e2e")
        client = ClaudeClient(api_key="test-key")
        mock_resp = _mock_claude_response(EMPTY_CLAUDE_RESPONSE)
        session = _mock_db_session()

        # Mock extract_from_url to return our local fixture
        doc = processor.extract_from_path(height_setback_pdf)

        pipeline = IngestionPipeline(
            pdf_processor=processor,
            claude_client=client,
            db_session=session,
        )

        with patch.object(processor, "extract_from_url", return_value=doc), \
             patch.object(client.client.messages, "create", return_value=mock_resp):
            result = await pipeline.ingest_document(
                name="Empty Response Test",
                url="http://example.com/test.pdf",
                specific_plan="Test Plan",
            )

        assert result.status == IngestionStatus.COMPLETED
        assert result.fragments_extracted == 0
        assert result.fragments_flagged == 0
        assert result.errors == []

    async def test_pipeline_handles_malformed_pdf(self, malformed_pdf: Path):
        """Malformed PDF -> FAILED status with error message."""
        processor = PdfProcessor(cache_dir="/tmp/test_pdfs_e2e")
        client = ClaudeClient(api_key="test-key")
        session = _mock_db_session()

        pipeline = IngestionPipeline(
            pdf_processor=processor,
            claude_client=client,
            db_session=session,
        )

        # extract_from_url will fail on our malformed file
        with patch.object(
            processor, "extract_from_url",
            side_effect=PdfExtractionError("Failed to parse PDF malformed.pdf"),
        ):
            result = await pipeline.ingest_document(
                name="Malformed Test",
                url="http://example.com/malformed.pdf",
                specific_plan="Bad Plan",
            )

        assert result.status == IngestionStatus.FAILED
        assert len(result.errors) >= 1
        assert "malformed" in result.errors[0].lower() or "failed" in result.errors[0].lower()

    async def test_full_pipeline_design_standards(self, design_standards_pdf: Path):
        """Real design standards PDF -> canned response -> design_standards field populated."""
        processor = PdfProcessor(cache_dir="/tmp/test_pdfs_e2e")
        doc = processor.extract_from_path(design_standards_pdf)
        chunks = processor.chunk_document(doc)

        client = ClaudeClient(api_key="test-key")
        mock_resp = _mock_claude_response(DESIGN_STANDARDS_CLAUDE_RESPONSE)

        all_fragments: list[ExtractedFragment] = []
        with patch.object(client.client.messages, "create", return_value=mock_resp):
            for chunk in chunks:
                fragments = client.extract_rule_fragments(
                    text_chunk=chunk,
                    document_name="Brentwood SP",
                    document_url="http://example.com/bwsp.pdf",
                )
                all_fragments.extend(fragments)

        assert len(all_fragments) == 2
        for frag in all_fragments:
            assert frag.constraint_type == "design_standard"
            assert frag.design_standards is not None
            assert len(frag.design_standards) >= 1

        material_frag = all_fragments[0]
        assert material_frag.design_standards[0]["category"] == "material"
        assert "stucco" in material_frag.design_standards[0]["allowed_values"]

        artic_frag = all_fragments[1]
        assert artic_frag.design_standards[0]["category"] == "articulation"
        assert artic_frag.design_standards[0]["numeric_value"] == 30

    async def test_markdown_fenced_response(self, height_setback_pdf: Path):
        """Claude response wrapped in markdown fences still parses correctly."""
        processor = PdfProcessor(cache_dir="/tmp/test_pdfs_e2e")
        doc = processor.extract_from_path(height_setback_pdf)
        chunks = processor.chunk_document(doc)

        client = ClaudeClient(api_key="test-key")
        mock_resp = _mock_claude_response(MARKDOWN_FENCED_RESPONSE)

        all_fragments: list[ExtractedFragment] = []
        with patch.object(client.client.messages, "create", return_value=mock_resp):
            for chunk in chunks:
                fragments = client.extract_rule_fragments(
                    text_chunk=chunk,
                    document_name="Fenced Test",
                    document_url="http://example.com/test.pdf",
                )
                all_fragments.extend(fragments)

        assert len(all_fragments) == 4
        assert {f.constraint_type for f in all_fragments} == {
            "height_max", "setback_front", "setback_side", "setback_rear",
        }

    async def test_ingest_document_stores_all_fragments(self, height_setback_pdf: Path):
        """Full ingest_document flow with mock download -> correct DB calls."""
        processor = PdfProcessor(cache_dir="/tmp/test_pdfs_e2e")
        doc = processor.extract_from_path(height_setback_pdf)

        client = ClaudeClient(api_key="test-key")
        mock_resp = _mock_claude_response(HEIGHT_SETBACK_CLAUDE_RESPONSE)
        session = _mock_db_session()

        pipeline = IngestionPipeline(
            pdf_processor=processor,
            claude_client=client,
            db_session=session,
        )

        with patch.object(processor, "extract_from_url", return_value=doc), \
             patch.object(client.client.messages, "create", return_value=mock_resp):
            result = await pipeline.ingest_document(
                name="Silver Lake SP",
                url="http://example.com/slsp.pdf",
                specific_plan="Silver Lake",
            )

        assert result.status == IngestionStatus.COMPLETED
        assert result.fragments_extracted == 4
        assert result.fragments_flagged == 0

        # 4 RuleFragment adds + 1 SpecificPlan add = 5 total
        assert session.add.call_count == 5

        # Verify all stored fragments have confidence='interpreted'
        for call in session.add.call_args_list[:4]:
            stored = call[0][0]
            assert stored.confidence == "interpreted"
            assert stored.specific_plan == "Silver Lake"
