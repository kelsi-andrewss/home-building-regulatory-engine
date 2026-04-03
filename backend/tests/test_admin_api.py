"""Integration tests for POST /api/admin/ingest endpoint."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

# Patch env before any app imports so Settings() can resolve database_url
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")

from backend.app.clients.claude_client import ExtractedFragment
from backend.app.db.models import RuleFragment, SpecificPlan
from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.services.pdf_processor import PdfDocument, PdfPage


def _mock_pdf_processor():
    mock = MagicMock()
    mock.extract_from_url.return_value = PdfDocument(
        filename="test.pdf",
        url="http://example.com/test.pdf",
        pages=[PdfPage(page_number=1, text="Section 7.B: Max height 33 feet.")],
        total_pages=1,
    )
    mock.chunk_document.return_value = [
        "[Pages 1-1]\nSection 7.B: Max height 33 feet."
    ]
    return mock


def _mock_claude_client():
    mock = MagicMock()
    mock.extract_rule_fragments.return_value = [
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
    return mock


VALID_PAYLOAD = {
    "name": "Test Specific Plan",
    "url": "http://example.com/test.pdf",
    "specific_plan": "Test Area Plan",
}


def _make_mock_session():
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    mock_session.close = AsyncMock()
    # _update_specific_plan SELECT returns None (no existing plan)
    mock_session.execute = AsyncMock(
        return_value=MagicMock(
            scalar_one_or_none=MagicMock(return_value=None)
        )
    )
    return mock_session


@pytest.mark.asyncio
class TestIngestEndpoint:
    async def test_ingest_success(self):
        """POST /api/admin/ingest with valid payload returns completed status."""
        mock_session = _make_mock_session()

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db
        try:
            with (
                patch(
                    "backend.app.api.admin.settings",
                    MagicMock(admin_api_key="test-key", anthropic_api_key="sk-test"),
                ),
                patch(
                    "backend.app.api.admin.PdfProcessor",
                    return_value=_mock_pdf_processor(),
                ),
                patch(
                    "backend.app.api.admin.ClaudeClient",
                    return_value=_mock_claude_client(),
                ),
            ):
                transport = httpx.ASGITransport(app=app)
                async with httpx.AsyncClient(
                    transport=transport, base_url="http://test"
                ) as client:
                    resp = await client.post(
                        "/api/admin/ingest",
                        json=VALID_PAYLOAD,
                        headers={"Authorization": "Bearer test-key"},
                    )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["document_name"] == "Test Specific Plan"
        assert data["fragments_extracted"] == 1
        assert data["fragments_flagged"] == 0

    async def test_ingest_no_auth_returns_401(self):
        """POST /api/admin/ingest without auth header returns 401."""
        with patch(
            "backend.app.api.admin.settings",
            MagicMock(admin_api_key="test-key", anthropic_api_key="sk-test"),
        ):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/api/admin/ingest",
                    json=VALID_PAYLOAD,
                )

        assert resp.status_code == 401

    async def test_ingest_no_anthropic_key_returns_503(self):
        """POST /api/admin/ingest without anthropic_api_key returns 503."""
        mock_session = _make_mock_session()

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db
        try:
            with patch(
                "backend.app.api.admin.settings",
                MagicMock(admin_api_key="test-key", anthropic_api_key=None),
            ):
                transport = httpx.ASGITransport(app=app)
                async with httpx.AsyncClient(
                    transport=transport, base_url="http://test"
                ) as client:
                    resp = await client.post(
                        "/api/admin/ingest",
                        json=VALID_PAYLOAD,
                        headers={"Authorization": "Bearer test-key"},
                    )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 503

    async def test_ingest_creates_rule_fragments(self):
        """Verify session.add is called with RuleFragment and SpecificPlan."""
        mock_session = _make_mock_session()
        added_objects: list = []
        mock_session.add = MagicMock(side_effect=lambda obj: added_objects.append(obj))

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db
        try:
            with (
                patch(
                    "backend.app.api.admin.settings",
                    MagicMock(admin_api_key="test-key", anthropic_api_key="sk-test"),
                ),
                patch(
                    "backend.app.api.admin.PdfProcessor",
                    return_value=_mock_pdf_processor(),
                ),
                patch(
                    "backend.app.api.admin.ClaudeClient",
                    return_value=_mock_claude_client(),
                ),
            ):
                transport = httpx.ASGITransport(app=app)
                async with httpx.AsyncClient(
                    transport=transport, base_url="http://test"
                ) as client:
                    resp = await client.post(
                        "/api/admin/ingest",
                        json=VALID_PAYLOAD,
                        headers={"Authorization": "Bearer test-key"},
                    )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 200

        rule_fragments = [o for o in added_objects if isinstance(o, RuleFragment)]
        specific_plans = [o for o in added_objects if isinstance(o, SpecificPlan)]
        assert len(rule_fragments) == 1
        assert rule_fragments[0].source_document == "Test Specific Plan"
        assert rule_fragments[0].specific_plan == "Test Area Plan"
        assert rule_fragments[0].confidence == "interpreted"
        assert len(specific_plans) == 1
        assert specific_plans[0].name == "Test Area Plan"
        assert specific_plans[0].ingestion_status == "completed"
