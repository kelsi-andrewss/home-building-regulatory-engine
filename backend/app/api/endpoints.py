import json
import logging
import uuid
from datetime import UTC, datetime, timedelta


def _utcnow() -> datetime:
    """Naive UTC timestamp compatible with asyncpg's 'timestamp without time zone'."""
    return datetime.now(UTC).replace(tzinfo=None)

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.db.models import Assessment, Parcel, Zone
from backend.app.db.session import get_db
from backend.app.engine.rule_engine import ConstraintResolver
from backend.app.engine.zone_parser import parse_zone
from backend.app.schemas.assessment import (
    AssessmentResponse,
    AssessRequest,
    BuildingTypeAssessment,
    ChatChunk,
    ChatRequest,
    Constraint,
    ParcelData,
    ParcelResponse,
    ZoningData,
)
from backend.app.schemas.design_constraints import (
    DesignConstraintRequest,
    DesignConstraintResponse,
    EdgeSetback,
    HeightEnvelope,
    MaterialRequirement,
    PanelFitResponse,
)
from backend.app.services.parcel_service import ParcelService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

CACHE_TTL = timedelta(hours=24)


def _parcel_service() -> ParcelService:
    import httpx

    from backend.app.clients.cams_client import CAMSClient
    from backend.app.clients.lacounty_client import LACountyClient
    from backend.app.clients.navigatela_client import NavigateLAClient

    session = httpx.AsyncClient(timeout=30.0)
    return ParcelService(
        cams=CAMSClient(session),
        lacounty=LACountyClient(session),
        navigatela=NavigateLAClient(session),
    )


def _constraint_resolver() -> ConstraintResolver:
    return ConstraintResolver()


def _to_parcel_data(parcel: Parcel) -> ParcelData:
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


def _to_zoning_data(zone: Zone) -> ZoningData:
    return ZoningData(
        zone_complete=zone.zone_complete,
        zone_class=zone.zone_class,
        height_district=zone.height_district,
        general_plan_land_use=zone.general_plan_land_use or "",
        specific_plan=zone.specific_plan_name,
        historic_overlay=zone.historic_overlay,
    )


def _resolved_to_schema(bta) -> BuildingTypeAssessment:
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
            )
            for c in bta.constraints
        ],
        max_buildable_area_sf=bta.max_size_sf,
        max_units=bta.max_units,
    )


@router.get("/geocode")
async def geocode(q: str):
    import httpx

    from backend.app.clients.cams_client import CAMSClient
    from backend.app.clients.lacounty_client import LACountyClient, ParcelNotFoundError

    session = httpx.AsyncClient(timeout=30.0)
    cams = CAMSClient(session)
    lacounty = LACountyClient(session)

    try:
        locations = await cams.geocode_many(q, max_locations=5)
    except Exception:
        logger.exception("Geocode failed for query: %s", q)
        return []

    import asyncio

    async def enrich(loc):
        try:
            parcel = await lacounty.get_parcel_at_point(loc.lat, loc.lng)
            apn = parcel.apn
        except ParcelNotFoundError:
            apn = ""
        except Exception:
            logger.exception("Parcel lookup failed for %s (%.5f, %.5f)", loc.address, loc.lat, loc.lng)
            apn = ""
        return {
            "address": loc.address,
            "apn": apn,
            "coordinates": [loc.lng, loc.lat],
        }

    results = await asyncio.gather(*[enrich(loc) for loc in locations])
    await session.aclose()

    # Deduplicate by APN, drop candidates with no parcel match
    seen = set()
    unique = []
    for r in results:
        if not r["apn"] or r["apn"] in seen:
            continue
        seen.add(r["apn"])
        unique.append(r)
    return unique


@router.post("/assess", response_model=AssessmentResponse)
async def assess(
    req: AssessRequest,
    db: AsyncSession = Depends(get_db),
    parcel_svc: ParcelService = Depends(_parcel_service),
    resolver: ConstraintResolver = Depends(_constraint_resolver),
) -> AssessmentResponse:
    try:
        return await _assess_inner(req, db, parcel_svc, resolver)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unhandled error in /assess")
        raise HTTPException(status_code=500, detail=str(exc))


async def _assess_inner(req, db, parcel_svc, resolver):
    try:
        if req.address:
            parcel_data = await parcel_svc.lookup_by_address(req.address)
        else:
            parcel_data = await parcel_svc.lookup_by_address(req.apn)
    except Exception as exc:
        logger.error("ParcelService lookup failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Upstream lookup failed: {exc}")

    if parcel_data is None:
        raise HTTPException(status_code=404, detail="Parcel not found")

    # Persist or update parcel
    result = await db.execute(select(Parcel).where(Parcel.apn == parcel_data.apn))
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
        db.add(parcel_row)
        await db.flush()

    # Persist or update zone
    zoning = parcel_data.zoning
    result = await db.execute(
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
        db.add(zone_row)
        await db.flush()

    # Run rule engine
    parsed_zone = parse_zone(zone_row.zone_complete)
    parcel_dict = {
        "lot_area_sf": parcel_row.lot_area_sf or 0,
        "geometry": parcel_data.geometry,
    }

    # Load rule fragments from DB
    from backend.app.db.models import RuleFragment

    frag_result = await db.execute(select(RuleFragment))
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

    resolved = resolver.resolve(
        parsed_zone=parsed_zone,
        parcel_data=parcel_dict,
        rule_fragments=rule_fragments,
        specific_plan=zone_row.specific_plan_name,
    )

    building_types = [_resolved_to_schema(bt) for bt in resolved.building_types]

    # Build summary (simple text fallback since SynthesisService may not exist yet)
    summary_parts = [f"Assessment for {parcel_data.address} (APN: {parcel_data.apn})"]
    summary_parts.append(f"Zone: {zone_row.zone_complete}")
    for bt in building_types:
        status = "Allowed" if bt.allowed else "Not allowed"
        summary_parts.append(f"  {bt.type}: {status}")
    summary = "\n".join(summary_parts)

    # Persist assessment
    assessment_id = uuid.uuid4()
    assessment_row = Assessment(
        id=assessment_id,
        parcel_id=parcel_row.id,
        zone_id=zone_row.id,
        request_address=req.address,
        request_apn=req.apn,
        result={
            "building_types": [bt.model_dump() for bt in building_types],
            "setback_geometry": resolved.setback_geometry,
        },
        summary=summary,
    )
    db.add(assessment_row)
    await db.flush()

    parcel_resp = _to_parcel_data(parcel_row)
    parcel_resp.geometry = parcel_data.geometry
    zoning_resp = _to_zoning_data(zone_row)

    return AssessmentResponse(
        parcel=parcel_resp,
        zoning=zoning_resp,
        building_types=building_types,
        setback_geometry=resolved.setback_geometry,
        summary=summary,
        assessment_id=assessment_id,
    )


@router.get("/parcel/{apn}", response_model=ParcelResponse)
async def get_parcel(
    apn: str,
    db: AsyncSession = Depends(get_db),
    parcel_svc: ParcelService = Depends(_parcel_service),
) -> ParcelResponse:
    result = await db.execute(
        select(Parcel)
        .where(Parcel.apn == apn)
        .options(selectinload(Parcel.zones))
    )
    parcel_row = result.scalars().first()

    now = _utcnow()

    if parcel_row and parcel_row.fetched_at and (now - parcel_row.fetched_at) < CACHE_TTL:
        zone_row = parcel_row.zones[0] if parcel_row.zones else None
        if zone_row:
            return ParcelResponse(
                parcel=_to_parcel_data(parcel_row),
                zoning=_to_zoning_data(zone_row),
            )

    # Cache miss or stale -- fetch fresh
    try:
        parcel_data = await parcel_svc.lookup_by_address(apn)
    except Exception as exc:
        logger.error("ParcelService lookup failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Upstream lookup failed: {exc}")

    if parcel_data is None:
        raise HTTPException(status_code=404, detail="Parcel not found")

    if not parcel_row:
        parcel_row = Parcel(
            apn=parcel_data.apn,
            address=parcel_data.address,
            lot_area_sf=parcel_data.lot_area_sf,
            year_built=parcel_data.year_built,
            existing_units=parcel_data.existing_units,
            existing_sqft=parcel_data.existing_sqft,
            raw_api_response={"geometry": parcel_data.geometry},
            fetched_at=now,
        )
        db.add(parcel_row)
        await db.flush()
    else:
        parcel_row.fetched_at = now
        await db.flush()

    zoning = parcel_data.zoning
    zone_row = Zone(
        parcel_id=parcel_row.id,
        zone_complete=zoning.zone_complete,
        zone_class=zoning.zone_class,
        height_district=parse_zone(zoning.zone_complete).height_district,
        general_plan_land_use=zoning.general_plan_land_use,
        specific_plan_name=zoning.specific_plan,
        historic_overlay=zoning.hpoz,
        fetched_at=now,
    )
    db.add(zone_row)
    await db.flush()

    parcel_resp = _to_parcel_data(parcel_row)
    parcel_resp.geometry = parcel_data.geometry

    return ParcelResponse(
        parcel=parcel_resp,
        zoning=_to_zoning_data(zone_row),
    )


@router.post("/chat")
async def chat(
    req: ChatRequest,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    result = await db.execute(
        select(Assessment)
        .where(Assessment.id == req.assessment_id)
        .options(
            selectinload(Assessment.parcel),
            selectinload(Assessment.zone),
        )
    )
    assessment = result.scalars().first()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    # Build context for Claude
    context = {
        "parcel": {
            "apn": assessment.parcel.apn,
            "address": assessment.parcel.address,
            "lot_area_sf": assessment.parcel.lot_area_sf,
        },
        "zoning": {
            "zone_complete": assessment.zone.zone_complete,
            "zone_class": assessment.zone.zone_class,
            "height_district": assessment.zone.height_district,
        },
        "result": assessment.result,
        "summary": assessment.summary,
    }

    system_message = (
        "You are a home building regulatory expert for Los Angeles. "
        "Answer questions about what can be built on this parcel based on the assessment data.\n\n"
        f"Assessment context:\n{json.dumps(context, indent=2)}"
    )

    import anthropic

    client = anthropic.AsyncAnthropic()

    async def stream_sse():
        try:
            async with client.messages.stream(
                model="claude-sonnet-4-20250514",
                max_tokens=2048,
                system=system_message,
                messages=[{"role": "user", "content": req.message}],
            ) as stream:
                async for text in stream.text_stream:
                    chunk = ChatChunk(content=text, done=False)
                    yield f"data: {chunk.model_dump_json()}\n\n"

            final = ChatChunk(content="", done=True)
            yield f"data: {final.model_dump_json()}\n\n"
        except Exception as exc:
            logger.error("Claude streaming failed: %s", exc)
            error_chunk = ChatChunk(content=f"Error: {exc}", done=True)
            yield f"data: {error_chunk.model_dump_json()}\n\n"

    return StreamingResponse(stream_sse(), media_type="text/event-stream")


@router.post("/design-constraints", response_model=DesignConstraintResponse)
async def get_design_constraints(
    req: DesignConstraintRequest,
    db: AsyncSession = Depends(get_db),
    parcel_svc: ParcelService = Depends(_parcel_service),
    resolver: ConstraintResolver = Depends(_constraint_resolver),
) -> DesignConstraintResponse:
    # 1. Parcel lookup
    try:
        if req.address:
            parcel_data = await parcel_svc.lookup_by_address(req.address)
        else:
            parcel_data = await parcel_svc.lookup_by_address(req.apn)
    except Exception as exc:
        logger.error("ParcelService lookup failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Upstream lookup failed: {exc}")

    if parcel_data is None:
        raise HTTPException(status_code=404, detail="Parcel not found")

    # 2. Persist or update parcel
    result = await db.execute(select(Parcel).where(Parcel.apn == parcel_data.apn))
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
        db.add(parcel_row)
        await db.flush()

    # 3. Persist or update zone
    zoning = parcel_data.zoning
    result = await db.execute(
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
        db.add(zone_row)
        await db.flush()

    # 4. Run rule engine
    parsed_zone = parse_zone(zone_row.zone_complete)
    parcel_dict = {
        "lot_area_sf": parcel_row.lot_area_sf or 0,
        "geometry": parcel_data.geometry,
    }

    from backend.app.db.models import RuleFragment

    frag_result = await db.execute(select(RuleFragment))
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

    resolved = resolver.resolve(
        parsed_zone=parsed_zone,
        parcel_data=parcel_dict,
        rule_fragments=rule_fragments,
        specific_plan=zone_row.specific_plan_name,
    )

    # 5. Extract constraint values directly from resolved constraints
    from backend.app.engine.rule_engine import _get_constraint_value

    # Use SFH constraints (first building type)
    sfh_constraints = resolved.building_types[0].constraints if resolved.building_types else []

    front_val = _get_constraint_value(sfh_constraints, "setback_front", 20.0)
    side_val = _get_constraint_value(sfh_constraints, "setback_side", 5.0)
    rear_val = _get_constraint_value(sfh_constraints, "setback_rear", 15.0)
    height_val = _get_constraint_value(sfh_constraints, "height_max", 33.0)

    # Build confidence/citation lookup from resolved constraints
    def _constraint_meta(constraints, name):
        for c in constraints:
            if c.constraint_type == name:
                return c.confidence.value, c.citation
        return "unknown", ""

    front_conf, front_cite = _constraint_meta(sfh_constraints, "setback_front")
    side_conf, side_cite = _constraint_meta(sfh_constraints, "setback_side")
    rear_conf, rear_cite = _constraint_meta(sfh_constraints, "setback_rear")
    height_conf, height_cite = _constraint_meta(sfh_constraints, "height_max")

    # 6. Edge geometry + envelope
    parcel_geojson = parcel_data.geometry
    if not parcel_geojson or not parcel_geojson.get("coordinates"):
        raise HTTPException(status_code=404, detail="Parcel has no geometry")

    from shapely.geometry import mapping

    from backend.app.engine.geometry_utils import (
        buffer_inward_per_edge,
        classify_parcel_edges,
        parcel_polygon_from_geojson,
    )
    from backend.app.engine.panel_fit import check_panel_fit

    parcel_poly = parcel_polygon_from_geojson(parcel_geojson)
    edges = classify_parcel_edges(parcel_poly)

    buffer_setbacks = {"front": front_val, "side": side_val, "rear": rear_val}
    envelope_poly = buffer_inward_per_edge(parcel_poly, edges, buffer_setbacks)
    envelope_geojson = mapping(envelope_poly)

    # 7. Panel fit
    panel_result = check_panel_fit(envelope_geojson, edges, side_val)

    # 8. Build response
    per_edge_setbacks = [
        EdgeSetback(edge="front", setback_ft=front_val, confidence=front_conf, citation=front_cite),
        EdgeSetback(edge="left_side", setback_ft=side_val, confidence=side_conf, citation=side_cite),
        EdgeSetback(edge="right_side", setback_ft=side_val, confidence=side_conf, citation=side_cite),
        EdgeSetback(edge="rear", setback_ft=rear_val, confidence=rear_conf, citation=rear_cite),
    ]

    height_envelope = HeightEnvelope(
        max_height_ft=height_val, confidence=height_conf, citation=height_cite
    )

    # Extract material requirements from resolved constraints
    material_requirements: list[MaterialRequirement] = []
    for c in sfh_constraints:
        if c.constraint_type.startswith("material_") or c.constraint_type == "fire_rating":
            material_requirements.append(
                MaterialRequirement(
                    requirement=f"{c.value} {c.unit}",
                    source=c.citation,
                    confidence=c.confidence.value,
                )
            )

    panel_fit = PanelFitResponse(
        feasible=panel_result.feasible,
        min_side_clearance_ft=panel_result.min_side_clearance,
        min_envelope_width_ft=panel_result.min_envelope_width,
        failures=panel_result.failures,
        mitigations=panel_result.mitigations,
    )

    return DesignConstraintResponse(
        parcel_apn=parcel_data.apn,
        envelope_geojson=envelope_geojson,
        per_edge_setbacks=per_edge_setbacks,
        height_envelope=height_envelope,
        material_requirements=material_requirements,
        panel_fit=panel_fit,
    )
