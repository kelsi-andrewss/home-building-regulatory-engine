import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.clients.claude_client import ClaudeClient, ExtractedFragment
from backend.app.services.ingestion_pipeline import IngestionPipeline, IngestionStatus
from backend.app.services.pdf_processor import PdfDocument, PdfPage, PdfProcessor


# -- PdfProcessor tests --


class TestChunkDocument:
    def test_splits_at_page_boundaries(self):
        """20 pages with a low token limit should produce multiple chunks at page boundaries."""
        processor = PdfProcessor(cache_dir="/tmp/test_pdfs")
        pages = [
            PdfPage(page_number=i + 1, text=f"Page {i + 1} content. " * 200)
            for i in range(20)
        ]
        doc = PdfDocument(filename="test.pdf", url="http://example.com/test.pdf",
                          pages=pages, total_pages=20)

        # ~4400 chars per page, limit to ~2 pages per chunk
        chunks = processor.chunk_document(doc, max_tokens=2500)

        assert len(chunks) > 1
        # Verify no text is lost: all pages appear across chunks
        all_text = " ".join(chunks)
        for i in range(20):
            assert f"Page {i + 1} content" in all_text

        # Verify each chunk has page range header
        for chunk in chunks:
            assert chunk.startswith("[Pages ")

    def test_single_page_fits_in_one_chunk(self):
        processor = PdfProcessor(cache_dir="/tmp/test_pdfs")
        doc = PdfDocument(
            filename="small.pdf", url="",
            pages=[PdfPage(page_number=1, text="Short text")],
            total_pages=1,
        )
        chunks = processor.chunk_document(doc, max_tokens=80_000)
        assert len(chunks) == 1

    def test_empty_document(self):
        processor = PdfProcessor(cache_dir="/tmp/test_pdfs")
        doc = PdfDocument(filename="empty.pdf", url="", pages=[], total_pages=0)
        chunks = processor.chunk_document(doc)
        assert chunks == []


# -- ClaudeClient tests --


VALID_CLAUDE_RESPONSE = json.dumps([
    {
        "constraint_type": "height_max",
        "value": 33,
        "unit": "ft",
        "condition": None,
        "zone_applicability": ["all"],
        "overrides_base_zone": True,
        "override_behavior": "replace",
        "source_section": "Section 7.B",
        "source_page": 12,
        "extraction_reasoning": "The plan states 'maximum height shall be 33 feet'.",
    },
    {
        "constraint_type": "setback_front",
        "value": 15,
        "unit": "ft",
        "condition": "for lots wider than 50 ft",
        "zone_applicability": ["R1", "RS"],
        "overrides_base_zone": False,
        "override_behavior": None,
        "source_section": "Section 9.A",
        "source_page": 18,
        "extraction_reasoning": "Section 9.A specifies 'a front yard setback of 15 feet for lots wider than 50 feet'.",
    },
])


VALID_DESIGN_STANDARD_RESPONSE = json.dumps([
    {
        "constraint_type": "design_standard",
        "value": None,
        "unit": "",
        "condition": None,
        "zone_applicability": ["all"],
        "overrides_base_zone": True,
        "override_behavior": "replace",
        "source_section": "Section 12.C",
        "source_page": 24,
        "extraction_reasoning": "Section 12.C specifies 'exterior materials shall be stucco, stone, or brick'.",
        "design_standards": [
            {
                "category": "material",
                "requirement_text": "Exterior materials shall be stucco, stone, or brick",
                "allowed_values": ["stucco", "stone", "brick"],
                "numeric_value": None,
                "numeric_unit": None,
                "applies_to": "facade",
            },
            {
                "category": "articulation",
                "requirement_text": "Minimum 30% facade articulation required",
                "allowed_values": None,
                "numeric_value": 30,
                "numeric_unit": "percent",
                "applies_to": "street-facing",
            },
            {
                "category": "color",
                "requirement_text": "Earth-tone color palette required",
                "allowed_values": ["earth-tone"],
                "numeric_value": None,
                "numeric_unit": None,
                "applies_to": "all",
            },
        ],
    },
])


class TestExtractRuleFragments:
    def test_parses_valid_json(self):
        """Mock API response with valid JSON -> correct ExtractedFragment objects."""
        client = ClaudeClient(api_key="test-key")

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=VALID_CLAUDE_RESPONSE)]

        with patch.object(client.client.messages, "create", return_value=mock_response):
            fragments = client.extract_rule_fragments(
                text_chunk="Some regulatory text",
                document_name="Test Plan",
                document_url="http://example.com/test.pdf",
            )

        assert len(fragments) == 2
        assert isinstance(fragments[0], ExtractedFragment)

        assert fragments[0].constraint_type == "height_max"
        assert fragments[0].value == 33
        assert fragments[0].unit == "ft"
        assert fragments[0].overrides_base_zone is True
        assert fragments[0].source_page == 12

        assert fragments[1].constraint_type == "setback_front"
        assert fragments[1].value == 15
        assert fragments[1].condition == "for lots wider than 50 ft"
        assert fragments[1].zone_applicability == ["R1", "RS"]

    def test_retries_on_429(self):
        """Mock API returning 429 then success -> verify retry."""
        import anthropic

        client = ClaudeClient(api_key="test-key")

        mock_success = MagicMock()
        mock_success.content = [MagicMock(text=VALID_CLAUDE_RESPONSE)]

        error_429 = anthropic.APIStatusError(
            message="Rate limited",
            response=MagicMock(status_code=429),
            body={"error": {"message": "rate limit"}},
        )

        with patch.object(
            client.client.messages, "create",
            side_effect=[error_429, mock_success],
        ):
            fragments = client.extract_rule_fragments(
                text_chunk="text",
                document_name="Test",
                document_url="http://example.com/test.pdf",
            )

        assert len(fragments) == 2
        assert fragments[0].constraint_type == "height_max"

    def test_handles_markdown_fenced_json(self):
        """Claude sometimes wraps JSON in markdown code fences."""
        client = ClaudeClient(api_key="test-key")

        fenced = f"```json\n{VALID_CLAUDE_RESPONSE}\n```"
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=fenced)]

        with patch.object(client.client.messages, "create", return_value=mock_response):
            fragments = client.extract_rule_fragments(
                text_chunk="text",
                document_name="Test",
                document_url="http://example.com/test.pdf",
            )

        assert len(fragments) == 2


# -- IngestionPipeline tests --


class TestValidateFragment:
    def _make_fragment(self, **kwargs) -> ExtractedFragment:
        defaults = {
            "constraint_type": "height_max",
            "value": 33,
            "unit": "ft",
            "condition": None,
            "zone_applicability": ["all"],
            "overrides_base_zone": True,
            "override_behavior": "replace",
            "source_section": "Section 1",
            "source_page": 1,
            "extraction_reasoning": "Test",
        }
        defaults.update(kwargs)
        return ExtractedFragment(**defaults)

    def test_flags_outlier_height(self):
        """height_max=500 should produce a warning."""
        pipeline = IngestionPipeline(
            pdf_processor=MagicMock(),
            claude_client=MagicMock(),
            db_session=MagicMock(),
        )
        fragment = self._make_fragment(value=500)
        warnings = pipeline.validate_fragment(fragment)
        assert len(warnings) == 1
        assert "above maximum" in warnings[0]

    def test_passes_valid_height(self):
        """height_max=33 should pass validation."""
        pipeline = IngestionPipeline(
            pdf_processor=MagicMock(),
            claude_client=MagicMock(),
            db_session=MagicMock(),
        )
        fragment = self._make_fragment(value=33)
        warnings = pipeline.validate_fragment(fragment)
        assert warnings == []

    def test_flags_negative_setback(self):
        """setback_front=-5 should produce a warning."""
        pipeline = IngestionPipeline(
            pdf_processor=MagicMock(),
            claude_client=MagicMock(),
            db_session=MagicMock(),
        )
        fragment = self._make_fragment(constraint_type="setback_front", value=-5)
        warnings = pipeline.validate_fragment(fragment)
        assert len(warnings) == 1
        assert "below minimum" in warnings[0]

    def test_skips_unknown_constraint_type(self):
        """Unknown constraint types should not be validated."""
        pipeline = IngestionPipeline(
            pdf_processor=MagicMock(),
            claude_client=MagicMock(),
            db_session=MagicMock(),
        )
        fragment = self._make_fragment(constraint_type="design_standard", value=999)
        warnings = pipeline.validate_fragment(fragment)
        assert warnings == []

    def test_skips_none_value(self):
        pipeline = IngestionPipeline(
            pdf_processor=MagicMock(),
            claude_client=MagicMock(),
            db_session=MagicMock(),
        )
        fragment = self._make_fragment(value=None)
        warnings = pipeline.validate_fragment(fragment)
        assert warnings == []


@pytest.mark.asyncio
class TestIngestDocumentEndToEnd:
    async def test_stores_fragments_with_interpreted_confidence(self):
        """Mock PDF + Claude response -> RuleFragment records with confidence='interpreted'."""
        mock_doc = PdfDocument(
            filename="test.pdf",
            url="http://example.com/test.pdf",
            pages=[PdfPage(page_number=1, text="Regulatory text here")],
            total_pages=1,
        )

        mock_pdf = MagicMock(spec=PdfProcessor)
        mock_pdf.extract_from_url.return_value = mock_doc
        mock_pdf.chunk_document.return_value = ["[Pages 1-1]\nRegulatory text here"]

        mock_claude = MagicMock(spec=ClaudeClient)
        mock_claude.extract_rule_fragments.return_value = [
            ExtractedFragment(
                constraint_type="height_max",
                value=33,
                unit="ft",
                condition=None,
                zone_applicability=["all"],
                overrides_base_zone=True,
                override_behavior="replace",
                source_section="Section 7.B",
                source_page=1,
                extraction_reasoning="Max height is 33 feet.",
            ),
        ]

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )

        pipeline = IngestionPipeline(
            pdf_processor=mock_pdf,
            claude_client=mock_claude,
            db_session=mock_session,
        )

        result = await pipeline.ingest_document(
            name="Test Plan",
            url="http://example.com/test.pdf",
            specific_plan="Test Area",
        )

        assert result.status == IngestionStatus.COMPLETED
        assert result.fragments_extracted == 1
        assert result.fragments_flagged == 0

        # Verify DB add was called with correct confidence
        # add is called twice: once for RuleFragment, once for SpecificPlan upsert
        assert mock_session.add.call_count == 2
        stored_fragment = mock_session.add.call_args_list[0][0][0]
        assert stored_fragment.confidence == "interpreted"
        assert stored_fragment.constraint_type == "height_max"
        assert stored_fragment.source_document == "Test Plan"


class TestDesignStandardExtraction:
    def test_parses_design_standard_with_sub_fields(self):
        """design_standard fragment should have populated design_standards list."""
        client = ClaudeClient(api_key="test-key")
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=VALID_DESIGN_STANDARD_RESPONSE)]

        with patch.object(client.client.messages, "create", return_value=mock_response):
            fragments = client.extract_rule_fragments(
                text_chunk="Some design standard text",
                document_name="Test Plan",
                document_url="http://example.com/test.pdf",
            )

        assert len(fragments) == 1
        frag = fragments[0]
        assert frag.constraint_type == "design_standard"
        assert frag.design_standards is not None
        assert len(frag.design_standards) == 3
        assert frag.design_standards[0]["category"] == "material"
        assert frag.design_standards[0]["allowed_values"] == ["stucco", "stone", "brick"]
        assert frag.design_standards[1]["category"] == "articulation"
        assert frag.design_standards[1]["numeric_value"] == 30
        assert frag.design_standards[2]["category"] == "color"

    def test_non_design_standard_has_no_design_standards_field(self):
        """height_max fragment should have design_standards=None even if LLM returns it."""
        client = ClaudeClient(api_key="test-key")
        bad_response = json.dumps([{
            "constraint_type": "height_max",
            "value": 33,
            "unit": "ft",
            "condition": None,
            "zone_applicability": ["all"],
            "overrides_base_zone": True,
            "override_behavior": "replace",
            "source_section": "Section 7",
            "source_page": 12,
            "extraction_reasoning": "Max height 33ft",
            "design_standards": [{"category": "material", "requirement_text": "oops"}],
        }])
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=bad_response)]

        with patch.object(client.client.messages, "create", return_value=mock_response):
            fragments = client.extract_rule_fragments(
                text_chunk="text", document_name="Test", document_url="http://example.com/test.pdf",
            )

        assert len(fragments) == 1
        assert fragments[0].constraint_type == "height_max"
        assert fragments[0].design_standards is None

    def test_design_standard_without_sub_fields_defaults_none(self):
        """design_standard fragment with no design_standards key -> design_standards=None."""
        client = ClaudeClient(api_key="test-key")
        response = json.dumps([{
            "constraint_type": "design_standard",
            "value": None,
            "unit": "",
            "condition": None,
            "zone_applicability": ["all"],
            "overrides_base_zone": True,
            "override_behavior": "replace",
            "source_section": "Section 5",
            "source_page": 8,
            "extraction_reasoning": "Some design standard",
        }])
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=response)]

        with patch.object(client.client.messages, "create", return_value=mock_response):
            fragments = client.extract_rule_fragments(
                text_chunk="text", document_name="Test", document_url="http://example.com/test.pdf",
            )

        assert len(fragments) == 1
        assert fragments[0].constraint_type == "design_standard"
        assert fragments[0].design_standards is None
