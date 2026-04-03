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
    if token != settings.admin_api_key:
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

    # Per-document breakdown
    fragments = (
        await db.execute(
            select(RuleFragment).order_by(
                RuleFragment.source_document, RuleFragment.constraint_type
            )
        )
    ).scalars().all()

    docs_map: dict[str, dict] = {}
    for f in fragments:
        doc = docs_map.setdefault(
            f.source_document,
            {
                "name": f.source_document,
                "fragment_count": 0,
                "fragments": [],
                "last_updated": None,
            },
        )
        doc["fragment_count"] += 1
        doc["fragments"].append(
            {
                "constraint_type": f.constraint_type,
                "value": f.value,
                "value_text": f.value_text,
                "unit": f.unit,
                "confidence": f.confidence,
                "source_section": f.source_section,
                "extraction_reasoning": f.extraction_reasoning,
            }
        )
        ts = f.extracted_at or f.created_at
        if doc["last_updated"] is None or ts > doc["last_updated"]:
            doc["last_updated"] = ts

    documents = []
    for doc in docs_map.values():
        doc["status"] = "ingested" if doc["fragment_count"] > 0 else "empty"
        doc["last_updated"] = (
            doc["last_updated"].isoformat() if doc["last_updated"] else None
        )
        documents.append(doc)

    return {
        "totalDocs": doc_count or 0,
        "totalFragments": frag_count or 0,
        "errorCount": confidence_distribution.get("unknown", 0),
        "confidenceDistribution": confidence_distribution,
        "documents": documents,
    }
