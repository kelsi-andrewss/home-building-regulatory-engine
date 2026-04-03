import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.clients.claude_client import ClaudeClient, ExtractedFragment
from backend.app.db.models import RuleFragment, SpecificPlan
from backend.app.services.pdf_processor import PdfProcessor

logger = logging.getLogger(__name__)


class IngestionStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class IngestionResult:
    document_name: str
    url: str
    status: IngestionStatus
    fragments_extracted: int = 0
    fragments_flagged: int = 0
    errors: list[str] = field(default_factory=list)


# Plausible validation ranges: constraint_type -> (min, max, unit)
VALIDATION_RANGES: dict[str, tuple[float, float]] = {
    "setback_front": (0, 50),
    "setback_side": (0, 50),
    "setback_rear": (0, 50),
    "height_max": (10, 100),
    "far_max": (0.1, 15),
    "density": (200, 20000),
    "lot_coverage": (1, 100),
    "lot_area_min": (1000, 100000),
    "lot_width_min": (20, 300),
}


class IngestionPipeline:
    """Orchestrates: download PDF -> extract text -> LLM structuring -> store + validate."""

    def __init__(
        self,
        pdf_processor: PdfProcessor,
        claude_client: ClaudeClient,
        db_session: AsyncSession,
    ):
        self.pdf_processor = pdf_processor
        self.claude_client = claude_client
        self.db_session = db_session

    async def ingest_document(
        self, name: str, url: str, specific_plan: str
    ) -> IngestionResult:
        """Full pipeline for a single document: download, extract, structure, store, validate.
        All fragments stored with confidence='interpreted'."""
        result = IngestionResult(
            document_name=name,
            url=url,
            status=IngestionStatus.PROCESSING,
        )

        try:
            # 1. Download and extract text
            doc = self.pdf_processor.extract_from_url(url)
            logger.info(
                "Extracted %d pages from %s", doc.total_pages, name
            )

            # 2. Chunk for Claude's context window
            chunks = self.pdf_processor.chunk_document(doc)
            logger.info("Split into %d chunks", len(chunks))

            # 3. Send each chunk to Claude and collect fragments
            all_fragments: list[ExtractedFragment] = []
            for i, chunk in enumerate(chunks):
                logger.info(
                    "Processing chunk %d/%d for %s", i + 1, len(chunks), name
                )
                try:
                    fragments = self.claude_client.extract_rule_fragments(
                        text_chunk=chunk,
                        document_name=name,
                        document_url=url,
                    )
                    all_fragments.extend(fragments)
                except Exception as e:
                    error_msg = f"Chunk {i + 1} failed: {e}"
                    logger.error(error_msg)
                    result.errors.append(error_msg)

            # 4. Validate and store each fragment
            for fragment in all_fragments:
                warnings = self.validate_fragment(fragment)
                if warnings:
                    result.fragments_flagged += 1
                    warning_text = "; ".join(warnings)
                    logger.warning(
                        "Outlier fragment in %s: %s", name, warning_text
                    )
                    # Append warning to extraction reasoning
                    fragment.extraction_reasoning = (
                        f"{fragment.extraction_reasoning} [VALIDATION WARNING: {warning_text}]"
                    )

                self._store_fragment(fragment, name, url, specific_plan)
                result.fragments_extracted += 1

            await self.db_session.flush()

            # 5. Upsert SpecificPlan record
            await self._update_specific_plan(
                specific_plan, result.fragments_extracted, url
            )

            result.status = IngestionStatus.COMPLETED
            await self.db_session.commit()
            logger.info(
                "Completed %s: %d fragments (%d flagged)",
                name, result.fragments_extracted, result.fragments_flagged,
            )

        except Exception as e:
            result.status = IngestionStatus.FAILED
            error_msg = f"Pipeline failed for {name}: {e}"
            logger.error(error_msg)
            result.errors.append(error_msg)

        return result

    async def ingest_all(
        self, manifest: list[dict]
    ) -> list[IngestionResult]:
        """Process all documents from the manifest sequentially."""
        results: list[IngestionResult] = []
        for entry in manifest:
            result = await self.ingest_document(
                name=entry["name"],
                url=entry["url"],
                specific_plan=entry["specific_plan"],
            )
            results.append(result)
        return results

    def validate_fragment(self, fragment: ExtractedFragment) -> list[str]:
        """Check a fragment against plausible ranges. Returns list of warning strings.
        Empty list = passed validation."""
        warnings: list[str] = []

        if fragment.constraint_type not in VALIDATION_RANGES:
            return warnings

        if fragment.value is None:
            return warnings

        min_val, max_val = VALIDATION_RANGES[fragment.constraint_type]
        if fragment.value < min_val:
            warnings.append(
                f"{fragment.constraint_type} value {fragment.value} below minimum {min_val}"
            )
        if fragment.value > max_val:
            warnings.append(
                f"{fragment.constraint_type} value {fragment.value} above maximum {max_val}"
            )

        return warnings

    def _store_fragment(
        self,
        fragment: ExtractedFragment,
        document_name: str,
        url: str,
        specific_plan: str,
    ) -> None:
        rule = RuleFragment(
            source_document=document_name,
            source_url=url,
            source_section=fragment.source_section,
            source_page=fragment.source_page,
            zone_applicability=fragment.zone_applicability,
            specific_plan=specific_plan,
            constraint_type=fragment.constraint_type,
            value=fragment.value,
            unit=fragment.unit,
            condition=fragment.condition,
            overrides_base_zone=fragment.overrides_base_zone,
            confidence="interpreted",
            extraction_reasoning=fragment.extraction_reasoning,
            extracted_at=datetime.now(timezone.utc),
        )
        self.db_session.add(rule)

    async def _update_specific_plan(
        self, plan_name: str, fragment_count: int, url: str
    ) -> None:
        """Upsert the SpecificPlan record with ingestion results."""
        from sqlalchemy import select

        stmt = select(SpecificPlan).where(SpecificPlan.name == plan_name)
        result = await self.db_session.execute(stmt)
        plan = result.scalar_one_or_none()
        if plan:
            plan.ingestion_status = "completed"
            plan.fragment_count = fragment_count
            plan.ingested_at = datetime.now(timezone.utc)
        else:
            plan = SpecificPlan(
                name=plan_name,
                source_pdf_url=url,
                ingestion_status="completed",
                fragment_count=fragment_count,
                ingested_at=datetime.now(timezone.utc),
            )
            self.db_session.add(plan)
