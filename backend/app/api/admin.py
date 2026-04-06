import hmac
import logging

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.clients.claude_client import ClaudeClient
from backend.app.config import settings
from backend.app.db.models import RuleFragment
from backend.app.db.session import get_db
from backend.app.schemas.admin import IngestRequest, IngestionResponse
from backend.app.services.ingestion_pipeline import IngestionPipeline
from backend.app.services.pdf_processor import PdfProcessor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin")


async def verify_admin_key(authorization: str | None = Header(None)) -> None:
    if settings.admin_api_key is None:
        raise HTTPException(status_code=401, detail="Admin endpoint disabled")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    token = authorization.removeprefix("Bearer ")
    if not hmac.compare_digest(settings.admin_api_key, token):
        raise HTTPException(status_code=401, detail="Invalid admin API key")


@router.post("/ingest", dependencies=[Depends(verify_admin_key)])
async def ingest_document(
    request: IngestRequest,
    db: AsyncSession = Depends(get_db),
) -> IngestionResponse:
    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=503,
            detail="Anthropic API key not configured",
        )

    pdf_processor = PdfProcessor()
    claude_client = ClaudeClient(api_key=settings.anthropic_api_key)
    pipeline = IngestionPipeline(pdf_processor, claude_client, db)

    result = await pipeline.ingest_document(
        request.name, request.url, request.specific_plan
    )

    return IngestionResponse(
        status=result.status.value,
        document_name=result.document_name,
        fragments_extracted=result.fragments_extracted,
        fragments_flagged=result.fragments_flagged,
        errors=result.errors,
    )


@router.get("/stats")
async def admin_stats(db: AsyncSession = Depends(get_db)):
    # Total distinct documents
    doc_count = await db.scalar(
        select(func.count(distinct(RuleFragment.source_document)))
    )

    # Total fragments
    frag_count = await db.scalar(select(func.count(RuleFragment.id)))

    # Confidence distribution
    conf_rows = (
        await db.execute(
            select(RuleFragment.confidence, func.count(RuleFragment.id))
            .group_by(RuleFragment.confidence)
        )
    ).all()
    confidence_distribution = {"verified": 0, "interpreted": 0, "unknown": 0}
    for level, count in conf_rows:
        if level in confidence_distribution:
            confidence_distribution[level] = count

    # Per-document breakdown (GROUP BY instead of loading all fragments)
    doc_rows = (
        await db.execute(
            select(
                RuleFragment.source_document,
                func.count(RuleFragment.id).label("fragment_count"),
                func.max(func.coalesce(RuleFragment.extracted_at, RuleFragment.created_at)).label("last_updated"),
            )
            .group_by(RuleFragment.source_document)
            .order_by(RuleFragment.source_document)
        )
    ).all()

    documents = [
        {
            "name": row.source_document,
            "fragment_count": row.fragment_count,
            "status": "ingested" if row.fragment_count > 0 else "empty",
            "last_updated": row.last_updated.isoformat() if row.last_updated else None,
        }
        for row in doc_rows
    ]

    return {
        "totalDocs": doc_count or 0,
        "totalFragments": frag_count or 0,
        "errorCount": confidence_distribution.get("unknown", 0),
        "confidenceDistribution": confidence_distribution,
        "documents": documents,
    }
