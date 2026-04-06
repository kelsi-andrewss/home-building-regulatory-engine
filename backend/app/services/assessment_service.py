import logging
import uuid
from datetime import UTC, datetime
from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models import Assessment, Parcel, RuleFragment, Zone
from backend.app.db.seed_data import SUPPORTED_ZONE_CLASSES
from backend.app.engine.rule_engine import ConstraintResolver
from backend.app.engine.zone_parser import parse_zone
from backend.app.schemas.assessment import (
    BuildingTypeAssessment,
    ConflictNote,
    Constraint,
    ParcelData,
    ZoningData,
)
from backend.app.services.parcel_service import ParcelService

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    """Naive UTC timestamp compatible with asyncpg's 'timestamp without time zone'."""
    return datetime.now(UTC).replace(tzinfo=None)


class LookupResult(NamedTuple):
    parcel_row: Parcel
    zone_row: Zone
    parcel_data: object  # ParcelService result
    parsed_zone: object  # ParsedZone from zone_parser
    resolved: object  # ResolvedConstraints from rule engine
    rule_fragments: list[dict]


class AssessmentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def resolve_parcel_and_zone(
        self,
        req,
        parcel_svc: ParcelService,
        resolver: ConstraintResolver,
    ) -> LookupResult:
        """Parcel lookup -> zone parse/validate -> DB upsert -> rule engine.
        Raises ValueError on unsupported zone, RuntimeError on lookup failure,
        LookupError on parcel not found. Caller maps to HTTPException."""
        # 1. Parcel lookup
        try:
            if req.address:
                parcel_data = await parcel_svc.lookup_by_address(req.address)
            else:
                parcel_data = await parcel_svc.lookup_by_apn(req.apn)
        except Exception as exc:
            logger.error("ParcelService lookup failed: %s", exc)
            raise RuntimeError(f"Upstream lookup failed: {exc}")

        if parcel_data is None:
            raise LookupError("Parcel not found")

        # 2. Validate zone is parseable and supported
        try:
            parsed = parse_zone(parcel_data.zoning.zone_complete)
        except ValueError as exc:
            raise ValueError(
                f"Zone '{parcel_data.zoning.zone_complete}' is not supported: {exc}"
            )

        if parsed.zone_class not in SUPPORTED_ZONE_CLASSES:
            raise ValueError(
                f"Zone '{parcel_data.zoning.zone_complete}' ({parsed.zone_class}) is not supported. "
                f"Supported zones: {', '.join(sorted(SUPPORTED_ZONE_CLASSES))}."
            )

        # 3. Persist or update parcel
        result = await self.db.execute(select(Parcel).where(Parcel.apn == parcel_data.apn))
        parcel_row = result.scalars().first()
        if not parcel_row:
            parcel_row = Parcel(
                apn=parcel_data.apn,
                address=parcel_data.address,
                lot_area_sf=parcel_data.lot_area_sf,
                year_built=parcel_data.year_built,
                existing_units=parcel_data.existing_units,
                existing_sqft=parcel_data.existing_sqft,
                raw_api_response={"geometry": parcel_data.geometry},
                fetched_at=_utcnow(),
            )
            self.db.add(parcel_row)
            await self.db.flush()

        # 4. Persist or update zone
        zoning = parcel_data.zoning
        result = await self.db.execute(
            select(Zone).where(
                Zone.parcel_id == parcel_row.id,
                Zone.zone_complete == zoning.zone_complete,
            )
        )
        zone_row = result.scalars().first()
        if not zone_row:
            zone_row = Zone(
                parcel_id=parcel_row.id,
                zone_complete=zoning.zone_complete,
                zone_class=zoning.zone_class,
                height_district=parse_zone(zoning.zone_complete).height_district,
                general_plan_land_use=zoning.general_plan_land_use,
                specific_plan_name=zoning.specific_plan,
                historic_overlay=zoning.hpoz,
                fetched_at=_utcnow(),
            )
            self.db.add(zone_row)
            await self.db.flush()

        # 5. Run rule engine
        parsed_zone = parse_zone(zone_row.zone_complete)
        parcel_dict = {
            "lot_area_sf": parcel_row.lot_area_sf or 0,
            "geometry": parcel_data.geometry,
        }

        # 6. Load rule fragments from DB
        frag_result = await self.db.execute(
            select(RuleFragment).where(RuleFragment.superseded_by.is_(None))
        )
        db_fragments = frag_result.scalars().all()
        rule_fragments = [
            {
                "constraint_type": f.constraint_type,
                "value": f.value,
                "unit": f.unit,
                "zone_applicability": f.zone_applicability,
                "specific_plan": f.specific_plan,
                "overrides_base_zone": f.overrides_base_zone,
                "source_document": f.source_document,
                "value_text": f.value_text or "",
                "extraction_reasoning": f.extraction_reasoning,
            }
            for f in db_fragments
        ]

        # Build project_params from request fields (if present)
        project_params = {}
        for field in ("bedrooms", "bathrooms", "sqft"):
            val = getattr(req, field, None)
            if val is not None:
                project_params[field] = val

        resolved = resolver.resolve(
            parsed_zone=parsed_zone,
            parcel_data=parcel_dict,
            rule_fragments=rule_fragments,
            specific_plan=zone_row.specific_plan_name,
            project_params=project_params or None,
        )

        return LookupResult(
            parcel_row=parcel_row,
            zone_row=zone_row,
            parcel_data=parcel_data,
            parsed_zone=parsed_zone,
            resolved=resolved,
            rule_fragments=rule_fragments,
        )

    def format_building_type(self, bta) -> BuildingTypeAssessment:
        """Engine BuildingTypeAssessment -> Pydantic BuildingTypeAssessment."""
        worst_confidence = "verified"
        for c in bta.constraints:
            if c.confidence.value == "unknown":
                worst_confidence = "unknown"
                break
            if c.confidence.value == "interpreted":
                worst_confidence = "interpreted"

        return BuildingTypeAssessment(
            type=bta.building_type.value,
            allowed=bta.allowed,
            confidence=worst_confidence,
            constraints=[
                Constraint(
                    name=c.constraint_type,
                    value=f"{c.value} {c.unit}",
                    confidence=c.confidence.value,
                    citation=c.citation,
                    explanation=c.explanation,
                    design_standards=getattr(c, "design_standards", False),
                    variance_available=getattr(c, "variance_available", False),
                    conflict_notes=getattr(c, "conflict_notes", None),
                )
                for c in bta.constraints
            ],
            max_buildable_area_sf=bta.max_size_sf,
            max_units=bta.max_units,
            max_bedrooms=bta.max_bedrooms,
        )

    def collect_conflicts(self, building_types: list) -> list[ConflictNote]:
        """Deduplicate conflict notes across all building types."""
        seen: set[str] = set()
        conflicts: list[ConflictNote] = []
        for bt in building_types:
            for c in bt.constraints:
                notes = getattr(c, "conflict_notes", None)
                if notes and c.constraint_type not in seen:
                    seen.add(c.constraint_type)
                    conflicts.append(ConflictNote(
                        constraint_name=c.constraint_type,
                        note=notes,
                        citation=c.citation,
                    ))
        return conflicts

    def build_summary(
        self,
        address: str,
        apn: str,
        zone: str,
        building_types: list[BuildingTypeAssessment],
    ) -> str:
        """Build human-readable summary text."""
        summary_parts = [f"Assessment for {address} (APN: {apn})"]
        summary_parts.append(f"Zone: {zone}")
        for bt in building_types:
            status = "Allowed" if bt.allowed else "Not allowed"
            summary_parts.append(f"  {bt.type}: {status}")
        return "\n".join(summary_parts)

    async def persist_assessment(
        self,
        parcel_row: Parcel,
        zone_row: Zone,
        req,
        building_types: list[BuildingTypeAssessment],
        setback_geometry: dict | None,
        summary: str,
    ) -> uuid.UUID:
        """Insert Assessment row, return its UUID."""
        assessment_id = uuid.uuid4()
        assessment_row = Assessment(
            id=assessment_id,
            parcel_id=parcel_row.id,
            zone_id=zone_row.id,
            request_address=req.address,
            request_apn=req.apn,
            result={
                "building_types": [bt.model_dump() for bt in building_types],
                "setback_geometry": setback_geometry,
            },
            summary=summary,
        )
        self.db.add(assessment_row)
        await self.db.flush()
        return assessment_id

    @staticmethod
    def to_parcel_data(parcel: Parcel) -> ParcelData:
        """ORM Parcel -> Pydantic ParcelData."""
        geom = parcel.raw_api_response.get("geometry", {}) if parcel.raw_api_response else {}
        return ParcelData(
            apn=parcel.apn,
            address=parcel.address or "",
            geometry=geom,
            lot_area_sf=parcel.lot_area_sf or 0.0,
            lot_width_ft=parcel.lot_width_ft,
            year_built=parcel.year_built,
            existing_units=parcel.existing_units,
            existing_sqft=parcel.existing_sqft,
        )

    @staticmethod
    def to_zoning_data(zone: Zone) -> ZoningData:
        """ORM Zone -> Pydantic ZoningData."""
        return ZoningData(
            zone_complete=zone.zone_complete,
            zone_class=zone.zone_class,
            height_district=zone.height_district,
            general_plan_land_use=zone.general_plan_land_use or "",
            specific_plan=zone.specific_plan_name,
            historic_overlay=zone.historic_overlay,
        )
