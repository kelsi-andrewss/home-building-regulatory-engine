from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from backend.app.engine.zone_parser import ParsedZone


class Confidence(str, Enum):
    VERIFIED = "verified"
    INTERPRETED = "interpreted"
    UNKNOWN = "unknown"


class BuildingType(str, Enum):
    SFH = "SFH"
    ADU = "ADU"
    GUEST_HOUSE = "Guest House"
    DUPLEX = "Duplex"


@dataclass
class ResolvedConstraint:
    constraint_type: str
    value: float
    unit: str
    confidence: Confidence
    citation: str
    explanation: str
    source: str
    variance_available: bool = True
    conflict_notes: str | None = None


@dataclass
class BuildingTypeAssessment:
    building_type: BuildingType
    allowed: bool
    constraints: list[ResolvedConstraint]
    max_units: int | None = None
    max_size_sf: float | None = None
    notes: str | None = None


@dataclass
class ResolvedAssessment:
    building_types: list[BuildingTypeAssessment]
    setback_geometry: dict | None = None
    summary_constraints: list[ResolvedConstraint] = field(default_factory=list)


# ---- Base zone rules (hand-coded from LAMC, Verified confidence) ----
# keyed by zone_class -> constraint_type -> {value, unit, citation}
BASE_ZONE_RULES: dict[str, dict[str, dict]] = {
    "RE9": {
        "min_lot_area": {"value": 9000, "unit": "sf", "citation": "LAMC SS12.07.01"},
        "min_lot_width": {"value": 65, "unit": "ft", "citation": "LAMC SS12.07.01"},
        "setback_front": {"value": 25, "unit": "ft", "citation": "LAMC SS12.07.01"},
        "setback_side": {"value": 10, "unit": "ft", "citation": "LAMC SS12.07.01"},
        "setback_rear": {"value": 25, "unit": "ft", "citation": "LAMC SS12.07.01"},
        "height_max": {"value": 33, "unit": "ft", "citation": "LAMC SS12.07.01"},
        "density": {"value": 1, "unit": "unit/lot", "citation": "LAMC SS12.07.01"},
    },
    "RE11": {
        "min_lot_area": {"value": 11000, "unit": "sf", "citation": "LAMC SS12.07.01"},
        "min_lot_width": {"value": 70, "unit": "ft", "citation": "LAMC SS12.07.01"},
        "setback_front": {"value": 25, "unit": "ft", "citation": "LAMC SS12.07.01"},
        "setback_side": {"value": 10, "unit": "ft", "citation": "LAMC SS12.07.01"},
        "setback_rear": {"value": 25, "unit": "ft", "citation": "LAMC SS12.07.01"},
        "height_max": {"value": 33, "unit": "ft", "citation": "LAMC SS12.07.01"},
        "density": {"value": 1, "unit": "unit/lot", "citation": "LAMC SS12.07.01"},
    },
    "RE15": {
        "min_lot_area": {"value": 15000, "unit": "sf", "citation": "LAMC SS12.07.01"},
        "min_lot_width": {"value": 80, "unit": "ft", "citation": "LAMC SS12.07.01"},
        "setback_front": {"value": 25, "unit": "ft", "citation": "LAMC SS12.07.01"},
        "setback_side": {"value": 10, "unit": "ft", "citation": "LAMC SS12.07.01"},
        "setback_rear": {"value": 25, "unit": "ft", "citation": "LAMC SS12.07.01"},
        "height_max": {"value": 33, "unit": "ft", "citation": "LAMC SS12.07.01"},
        "density": {"value": 1, "unit": "unit/lot", "citation": "LAMC SS12.07.01"},
    },
    "RE20": {
        "min_lot_area": {"value": 20000, "unit": "sf", "citation": "LAMC SS12.07.01"},
        "min_lot_width": {"value": 100, "unit": "ft", "citation": "LAMC SS12.07.01"},
        "setback_front": {"value": 25, "unit": "ft", "citation": "LAMC SS12.07.01"},
        "setback_side": {"value": 10, "unit": "ft", "citation": "LAMC SS12.07.01"},
        "setback_rear": {"value": 25, "unit": "ft", "citation": "LAMC SS12.07.01"},
        "height_max": {"value": 33, "unit": "ft", "citation": "LAMC SS12.07.01"},
        "density": {"value": 1, "unit": "unit/lot", "citation": "LAMC SS12.07.01"},
    },
    "RE40": {
        "min_lot_area": {"value": 40000, "unit": "sf", "citation": "LAMC SS12.07.01"},
        "min_lot_width": {"value": 150, "unit": "ft", "citation": "LAMC SS12.07.01"},
        "setback_front": {"value": 25, "unit": "ft", "citation": "LAMC SS12.07.01"},
        "setback_side": {"value": 10, "unit": "ft", "citation": "LAMC SS12.07.01"},
        "setback_rear": {"value": 25, "unit": "ft", "citation": "LAMC SS12.07.01"},
        "height_max": {"value": 33, "unit": "ft", "citation": "LAMC SS12.07.01"},
        "density": {"value": 1, "unit": "unit/lot", "citation": "LAMC SS12.07.01"},
    },
    "RS": {
        "min_lot_area": {"value": 7500, "unit": "sf", "citation": "LAMC SS12.07.1"},
        "min_lot_width": {"value": 60, "unit": "ft", "citation": "LAMC SS12.07.1"},
        "setback_front": {"value": 25, "unit": "ft", "citation": "LAMC SS12.07.1"},
        "setback_side": {"value": 5, "unit": "ft", "citation": "LAMC SS12.07.1"},
        "setback_rear": {"value": 20, "unit": "ft", "citation": "LAMC SS12.07.1"},
        "height_max": {"value": 33, "unit": "ft", "citation": "LAMC SS12.07.1"},
        "density": {"value": 1, "unit": "unit/lot", "citation": "LAMC SS12.07.1"},
    },
    "R1": {
        "min_lot_area": {"value": 5000, "unit": "sf", "citation": "LAMC SS12.08"},
        "min_lot_width": {"value": 50, "unit": "ft", "citation": "LAMC SS12.08"},
        "setback_front": {"value": 20, "unit": "ft", "citation": "LAMC SS12.08"},
        "setback_side": {"value": 5, "unit": "ft", "citation": "LAMC SS12.08"},
        "setback_rear": {"value": 15, "unit": "ft", "citation": "LAMC SS12.08"},
        "height_max": {"value": 33, "unit": "ft", "citation": "LAMC SS12.08"},
        "density": {"value": 1, "unit": "unit/lot", "citation": "LAMC SS12.08"},
    },
    "R2": {
        "min_lot_area": {"value": 5000, "unit": "sf", "citation": "LAMC SS12.09"},
        "min_lot_width": {"value": 50, "unit": "ft", "citation": "LAMC SS12.09"},
        "setback_front": {"value": 20, "unit": "ft", "citation": "LAMC SS12.09"},
        "setback_side": {"value": 5, "unit": "ft", "citation": "LAMC SS12.09"},
        "setback_rear": {"value": 15, "unit": "ft", "citation": "LAMC SS12.09"},
        "height_max": {"value": 33, "unit": "ft", "citation": "LAMC SS12.09"},
        "density": {"value": 2500, "unit": "sf", "citation": "LAMC SS12.09"},
    },
    "RD6": {
        "min_lot_area": {"value": 6000, "unit": "sf", "citation": "LAMC SS12.09.1"},
        "min_lot_width": {"value": 50, "unit": "ft", "citation": "LAMC SS12.09.1"},
        "setback_front": {"value": 20, "unit": "ft", "citation": "LAMC SS12.09.1"},
        "setback_side": {"value": 5, "unit": "ft", "citation": "LAMC SS12.09.1"},
        "setback_rear": {"value": 15, "unit": "ft", "citation": "LAMC SS12.09.1"},
        "height_max": {"value": 45, "unit": "ft", "citation": "LAMC SS12.09.1"},
        "density": {"value": 6000, "unit": "sf", "citation": "LAMC SS12.09.1"},
    },
    "RD5": {
        "min_lot_area": {"value": 5000, "unit": "sf", "citation": "LAMC SS12.09.1"},
        "min_lot_width": {"value": 50, "unit": "ft", "citation": "LAMC SS12.09.1"},
        "setback_front": {"value": 20, "unit": "ft", "citation": "LAMC SS12.09.1"},
        "setback_side": {"value": 5, "unit": "ft", "citation": "LAMC SS12.09.1"},
        "setback_rear": {"value": 15, "unit": "ft", "citation": "LAMC SS12.09.1"},
        "height_max": {"value": 45, "unit": "ft", "citation": "LAMC SS12.09.1"},
        "density": {"value": 5000, "unit": "sf", "citation": "LAMC SS12.09.1"},
    },
    "RD4": {
        "min_lot_area": {"value": 5000, "unit": "sf", "citation": "LAMC SS12.09.1"},
        "min_lot_width": {"value": 50, "unit": "ft", "citation": "LAMC SS12.09.1"},
        "setback_front": {"value": 20, "unit": "ft", "citation": "LAMC SS12.09.1"},
        "setback_side": {"value": 7.5, "unit": "ft", "citation": "LAMC SS12.09.1"},
        "setback_rear": {"value": 15, "unit": "ft", "citation": "LAMC SS12.09.1"},
        "height_max": {"value": 45, "unit": "ft", "citation": "LAMC SS12.09.1"},
        "density": {"value": 4000, "unit": "sf", "citation": "LAMC SS12.09.1"},
    },
    "RD3": {
        "min_lot_area": {"value": 5000, "unit": "sf", "citation": "LAMC SS12.09.1"},
        "min_lot_width": {"value": 50, "unit": "ft", "citation": "LAMC SS12.09.1"},
        "setback_front": {"value": 20, "unit": "ft", "citation": "LAMC SS12.09.1"},
        "setback_side": {"value": 7.5, "unit": "ft", "citation": "LAMC SS12.09.1"},
        "setback_rear": {"value": 15, "unit": "ft", "citation": "LAMC SS12.09.1"},
        "height_max": {"value": 45, "unit": "ft", "citation": "LAMC SS12.09.1"},
        "density": {"value": 3000, "unit": "sf", "citation": "LAMC SS12.09.1"},
    },
    "RD2": {
        "min_lot_area": {"value": 5000, "unit": "sf", "citation": "LAMC SS12.09.1"},
        "min_lot_width": {"value": 50, "unit": "ft", "citation": "LAMC SS12.09.1"},
        "setback_front": {"value": 20, "unit": "ft", "citation": "LAMC SS12.09.1"},
        "setback_side": {"value": 5, "unit": "ft", "citation": "LAMC SS12.09.1"},
        "setback_rear": {"value": 15, "unit": "ft", "citation": "LAMC SS12.09.1"},
        "height_max": {"value": 45, "unit": "ft", "citation": "LAMC SS12.09.1"},
        "density": {"value": 2000, "unit": "sf", "citation": "LAMC SS12.09.1"},
    },
    "RD1.5": {
        "min_lot_area": {"value": 5000, "unit": "sf", "citation": "LAMC SS12.09.1"},
        "min_lot_width": {"value": 50, "unit": "ft", "citation": "LAMC SS12.09.1"},
        "setback_front": {"value": 20, "unit": "ft", "citation": "LAMC SS12.09.1"},
        "setback_side": {"value": 5, "unit": "ft", "citation": "LAMC SS12.09.1"},
        "setback_rear": {"value": 15, "unit": "ft", "citation": "LAMC SS12.09.1"},
        "height_max": {"value": 45, "unit": "ft", "citation": "LAMC SS12.09.1"},
        "density": {"value": 1500, "unit": "sf", "citation": "LAMC SS12.09.1"},
    },
    "R3": {
        "min_lot_area": {"value": 5000, "unit": "sf", "citation": "LAMC SS12.10"},
        "min_lot_width": {"value": 50, "unit": "ft", "citation": "LAMC SS12.10"},
        "setback_front": {"value": 15, "unit": "ft", "citation": "LAMC SS12.10"},
        "setback_side": {"value": 5, "unit": "ft", "citation": "LAMC SS12.10"},
        "setback_rear": {"value": 15, "unit": "ft", "citation": "LAMC SS12.10"},
        "height_max": {"value": 45, "unit": "ft", "citation": "LAMC SS12.10"},
        "density": {"value": 800, "unit": "sf", "citation": "LAMC SS12.10"},
    },
    "R4": {
        "min_lot_area": {"value": 5000, "unit": "sf", "citation": "LAMC SS12.11"},
        "min_lot_width": {"value": 50, "unit": "ft", "citation": "LAMC SS12.11"},
        "setback_front": {"value": 15, "unit": "ft", "citation": "LAMC SS12.11"},
        "setback_side": {"value": 5, "unit": "ft", "citation": "LAMC SS12.11"},
        "setback_rear": {"value": 15, "unit": "ft", "citation": "LAMC SS12.11"},
        "height_max": {"value": 45, "unit": "ft", "citation": "LAMC SS12.11"},
        "density": {"value": 400, "unit": "sf", "citation": "LAMC SS12.11"},
    },
}

# ---- Height district modifiers ----
# keyed by HD string -> {height_sf, height_mf, far_mf}
HEIGHT_DISTRICT_MODIFIERS: dict[str, dict[str, float]] = {
    "1":   {"height_sf": 33, "height_mf": 45, "far_mf": 3.0},
    "1L":  {"height_sf": 33, "height_mf": 35, "far_mf": 3.0},
    "1VL": {"height_sf": 33, "height_mf": 33, "far_mf": 3.0},
    "1XL": {"height_sf": 33, "height_mf": 30, "far_mf": 3.0},
    "1SS": {"height_sf": 33, "height_mf": 30, "far_mf": 3.0},
}

# Single-family zone classes (height uses height_sf from HD modifier)
_SF_ZONES = {"RE9", "RE11", "RE15", "RE20", "RE40", "RS", "R1"}

# Zones that allow multi-family / duplex density
_DUPLEX_ZONES = {"R2", "RD1.5", "RD2", "RD3", "RD4", "RD5", "RD6", "R3", "R4"}

# SFH requires 2 covered parking spaces (LAMC SS12.21-A,4), ~400sf footprint.
# ADU parking waived under state law (SB 13).
_SFH_PARKING_FOOTPRINT_SF = 400

# Constraint types where "more restrictive" means LOWER value
_MAX_CONSTRAINTS = {"height_max", "far_max", "lot_coverage_max", "size_max_detached"}

# Constraint types where "more restrictive" means HIGHER value
_MIN_CONSTRAINTS = {"setback_front", "setback_side", "setback_rear", "min_lot_area", "min_lot_width"}


def tag_confidence(source: str, extraction_method: str | None = None) -> Confidence:
    if source in ("base_zone", "height_district", "adu_state_law"):
        return Confidence.VERIFIED
    if source in ("specific_plan", "overlay") and extraction_method:
        return Confidence.INTERPRETED
    return Confidence.UNKNOWN


def _is_single_family_zone(zone_class: str) -> bool:
    return zone_class in _SF_ZONES


def _allows_duplex(zone_class: str) -> bool:
    return zone_class in _DUPLEX_ZONES


def _filter_effective_rules(
    fragments: list[dict],
    as_of: datetime | None = None,
) -> list[dict]:
    """Drop fragments where superseded_by is set or effective_date is in the future."""
    if as_of is None:
        as_of = datetime.utcnow()
    result = []
    for f in fragments:
        if f.get("superseded_by") is not None:
            continue
        eff = f.get("effective_date")
        if eff is not None and eff > as_of:
            continue
        result.append(f)
    return result


def _detect_overlay_conflicts(
    base_constraints: list[ResolvedConstraint],
    overlay_constraints: list[ResolvedConstraint],
) -> dict[str, str]:
    """Compare overlay constraints against base. Return {constraint_type: conflict_note}
    for any constraint where the overlay contradicts the base direction
    (overlay is less restrictive than base).
    """
    base_index: dict[str, ResolvedConstraint] = {c.constraint_type: c for c in base_constraints}
    conflicts: dict[str, str] = {}
    for oc in overlay_constraints:
        ct = oc.constraint_type
        if ct not in base_index:
            continue
        bc = base_index[ct]
        is_conflict = False
        if ct in _MAX_CONSTRAINTS and oc.value > bc.value:
            is_conflict = True
        elif ct in _MIN_CONSTRAINTS and oc.value < bc.value:
            is_conflict = True
        if is_conflict:
            conflicts[ct] = (
                f"Overlay {oc.citation} sets {ct} to {oc.value}{oc.unit}, "
                f"contradicting base {bc.citation} ({bc.value}{bc.unit}). "
                f"Most restrictive value applied."
            )
    return conflicts


def _merge_constraints(
    base: list[ResolvedConstraint],
    overlay: list[ResolvedConstraint],
    overlay_overrides: bool = False,
    conflict_map: dict[str, str] | None = None,
) -> list[ResolvedConstraint]:
    """Merge two constraint lists. Most restrictive wins unless overlay_overrides=True."""
    if conflict_map is None:
        conflict_map = {}
    merged: dict[str, ResolvedConstraint] = {}
    for c in base:
        merged[c.constraint_type] = c

    for c in overlay:
        ct = c.constraint_type
        if ct not in merged or overlay_overrides:
            merged[ct] = c
            if ct in conflict_map:
                merged[ct].conflict_notes = conflict_map[ct]
            continue

        existing = merged[ct]
        # AND logic for variance_available: if either side says no, result says no
        combined_variance = existing.variance_available and c.variance_available
        conflict_note = conflict_map.get(ct)

        # Most restrictive: lower for max constraints, higher for min constraints
        if ct in _MAX_CONSTRAINTS:
            if c.value < existing.value:
                merged[ct] = ResolvedConstraint(
                    constraint_type=ct,
                    value=c.value,
                    unit=c.unit,
                    confidence=min(existing.confidence, c.confidence, key=_confidence_rank),
                    citation=c.citation,
                    explanation=f"Most restrictive: {c.citation} ({c.value}) vs {existing.citation} ({existing.value})",
                    source=c.source,
                    variance_available=combined_variance,
                    conflict_notes=conflict_note,
                )
            else:
                existing.variance_available = combined_variance
                if conflict_note:
                    existing.conflict_notes = conflict_note
        elif ct in _MIN_CONSTRAINTS:
            if c.value > existing.value:
                merged[ct] = ResolvedConstraint(
                    constraint_type=ct,
                    value=c.value,
                    unit=c.unit,
                    confidence=min(existing.confidence, c.confidence, key=_confidence_rank),
                    citation=c.citation,
                    explanation=f"Most restrictive: {c.citation} ({c.value}) vs {existing.citation} ({existing.value})",
                    source=c.source,
                    variance_available=combined_variance,
                    conflict_notes=conflict_note,
                )
            else:
                existing.variance_available = combined_variance
                if conflict_note:
                    existing.conflict_notes = conflict_note
        else:
            # Non-dimensional constraints (density, etc.): overlay wins if present
            c.variance_available = combined_variance
            merged[ct] = c

    return list(merged.values())


def _confidence_rank(c: Confidence) -> int:
    return {Confidence.VERIFIED: 2, Confidence.INTERPRETED: 1, Confidence.UNKNOWN: 0}[c]


class ConstraintResolver:
    """Merges base zone rules, specific plan rules, and ADU preemption into final constraints."""

    def resolve(
        self,
        parsed_zone: ParsedZone,
        parcel_data: dict,
        rule_fragments: list[dict],
        specific_plan: str | None = None,
        project_params: dict | None = None,
    ) -> ResolvedAssessment:
        # 1. Load base zone rules
        base_rules = BASE_ZONE_RULES.get(parsed_zone.zone_class, {})
        base_constraints = [
            ResolvedConstraint(
                constraint_type=ct,
                value=info["value"],
                unit=info["unit"],
                confidence=Confidence.VERIFIED,
                citation=info["citation"],
                explanation=f"Base zone {parsed_zone.zone_class} {ct}",
                source="base_zone",
            )
            for ct, info in base_rules.items()
        ]

        # 2. Apply height district modifiers
        hd_mods = HEIGHT_DISTRICT_MODIFIERS.get(parsed_zone.height_district, {})
        if hd_mods:
            is_sf = _is_single_family_zone(parsed_zone.zone_class)
            hd_height = hd_mods["height_sf"] if is_sf else hd_mods["height_mf"]
            hd_constraints = [
                ResolvedConstraint(
                    constraint_type="height_max",
                    value=hd_height,
                    unit="ft",
                    confidence=Confidence.VERIFIED,
                    citation=f"LAMC SS12.21.1, Height District {parsed_zone.height_district}",
                    explanation=f"Height District {parsed_zone.height_district} {'single-family' if is_sf else 'multi-family'} max",
                    source="height_district",
                ),
            ]
            if not is_sf:
                hd_constraints.append(ResolvedConstraint(
                    constraint_type="far_max",
                    value=hd_mods["far_mf"],
                    unit="ratio",
                    confidence=Confidence.VERIFIED,
                    citation=f"LAMC SS12.21.1, Height District {parsed_zone.height_district}",
                    explanation=f"Height District {parsed_zone.height_district} FAR",
                    source="height_district",
                ))

            base_constraints = _merge_constraints(base_constraints, hd_constraints)

        # 2.5. Filter out superseded / not-yet-effective fragments
        rule_fragments = _filter_effective_rules(rule_fragments)

        # 3. Filter and apply rule fragments
        # Build zone index for O(1) lookup instead of linear scan
        zone_index: dict[str, list[dict]] = {}
        all_zones: list[dict] = []
        for f in rule_fragments:
            applicability = f.get("zone_applicability") or []
            if "all" in applicability:
                all_zones.append(f)
            else:
                for zone in applicability:
                    zone_index.setdefault(zone, []).append(f)

        matching_fragments = zone_index.get(parsed_zone.zone_class, []) + all_zones

        if specific_plan:
            sp_fragments = [
                f for f in rule_fragments
                if f.get("specific_plan") == specific_plan
            ]
            matching_fragments.extend(sp_fragments)

        # Convert fragments to ResolvedConstraints and merge
        fragment_constraints: list[ResolvedConstraint] = []
        fragment_overrides = False
        for frag in matching_fragments:
            if frag.get("value") is None:
                continue
            confidence = tag_confidence(
                "specific_plan" if frag.get("specific_plan") else "base_zone",
                frag.get("extraction_reasoning"),
            )
            fragment_constraints.append(ResolvedConstraint(
                constraint_type=frag["constraint_type"],
                value=frag["value"],
                unit=frag.get("unit", ""),
                confidence=confidence,
                citation=frag.get("source_document", ""),
                explanation=frag.get("value_text", ""),
                source="specific_plan" if frag.get("specific_plan") else "base_zone",
                variance_available=frag.get("variance_available", True),
            ))
            if frag.get("overrides_base_zone"):
                fragment_overrides = True

        if fragment_constraints:
            conflict_map = _detect_overlay_conflicts(base_constraints, fragment_constraints)
            base_constraints = _merge_constraints(
                base_constraints, fragment_constraints,
                overlay_overrides=fragment_overrides,
                conflict_map=conflict_map,
            )

        # 4. Compute FAR-based max buildable area for sqft validation
        lot_area = parcel_data.get("lot_area_sf", 0)
        params = project_params or {}
        proposed_sqft = params.get("sqft")
        far_max = _get_constraint_value(base_constraints, "far_max", 0.0)
        max_buildable_sf: float | None = None
        if far_max > 0 and lot_area > 0:
            max_buildable_sf = lot_area * far_max

        # 4a. Compute min sqft from bedrooms + bathrooms
        bedrooms = params.get("bedrooms")
        bathrooms = params.get("bathrooms")
        min_sqft: float | None = None
        undersized_note: str | None = None
        if bedrooms is not None or bathrooms is not None:
            min_sqft = (bedrooms or 0) * 120 + (bathrooms or 0) * 40 + 200
            if proposed_sqft is not None and proposed_sqft < min_sqft:
                undersized_note = (
                    f"Proposed {proposed_sqft:,.0f} sf may be undersized for "
                    f"{bedrooms or 0} bed / {bathrooms or 0} bath "
                    f"(minimum ~{min_sqft:,.0f} sf)"
                )

        # 4b. Effective sqft for FAR comparison: use proposed_sqft if set,
        # otherwise fall back to min_sqft from bedrooms/bathrooms.
        effective_sqft = proposed_sqft if proposed_sqft is not None else min_sqft

        # 4c. Parking footprint deduction: SFH/Guest House/Duplex need covered
        # parking (~400sf). ADU parking is waived (SB 13).
        max_livable_sf: float | None = None
        if max_buildable_sf is not None:
            max_livable_sf = max_buildable_sf - _SFH_PARKING_FOOTPRINT_SF

        sqft_exceeds = (
            effective_sqft is not None
            and max_livable_sf is not None
            and effective_sqft > max_livable_sf
        )
        sqft_note: str | None = None
        if sqft_exceeds:
            sqft_note = (
                f"Proposed {effective_sqft:,.0f} sf exceeds max buildable area "
                f"of {max_buildable_sf:,.0f} sf "
                f"(FAR {far_max} \u00d7 {lot_area:,.0f} sf lot, "
                f"minus {_SFH_PARKING_FOOTPRINT_SF} sf parking)"
            )

        # 5. Build per-building-type assessments
        summary_constraints = list(base_constraints)
        building_types: list[BuildingTypeAssessment] = []

        # SFH -- always allowed in residential zones (unless sqft exceeds FAR limit)
        sfh_notes_parts: list[str] = []
        if sqft_note:
            sfh_notes_parts.append(sqft_note)
        if undersized_note:
            sfh_notes_parts.append(undersized_note)
        sfh_notes = "; ".join(sfh_notes_parts) if sfh_notes_parts else None

        building_types.append(BuildingTypeAssessment(
            building_type=BuildingType.SFH,
            allowed=not sqft_exceeds,
            constraints=list(base_constraints),
            max_units=1,
            max_size_sf=max_buildable_sf,
            notes=sfh_notes,
        ))

        # ADU -- always allowed by state law (no parking deduction)
        from backend.app.engine.adu_preemption import apply_adu_preemption
        adu_result = apply_adu_preemption(list(base_constraints))
        adu_max_size = 1200.0
        if project_params and "sqft" in project_params:
            requested = project_params["sqft"]
            if requested < adu_max_size:
                adu_max_size = requested
        building_types.append(BuildingTypeAssessment(
            building_type=BuildingType.ADU,
            allowed=True,
            constraints=adu_result.constraints,
            max_units=1,
            max_size_sf=adu_max_size,
            notes="; ".join(adu_result.preemptions_applied) if adu_result.preemptions_applied else None,
        ))

        # Guest House -- same as SFH, accessory structure
        guest_house_notes_parts = ["Accessory structure; same setback/height rules as primary dwelling"]
        if sqft_note:
            guest_house_notes_parts.append(sqft_note)
        if undersized_note:
            guest_house_notes_parts.append(undersized_note)
        guest_house_notes = "; ".join(guest_house_notes_parts)
        building_types.append(BuildingTypeAssessment(
            building_type=BuildingType.GUEST_HOUSE,
            allowed=not sqft_exceeds,
            constraints=list(base_constraints),
            max_units=1,
            max_size_sf=max_buildable_sf,
            notes=guest_house_notes,
        ))

        # Duplex -- only in R2+ and RD zones
        duplex_allowed = _allows_duplex(parsed_zone.zone_class)
        density_rule = base_rules.get("density", {})
        density_value = density_rule.get("value", 0)
        density_unit = density_rule.get("unit", "")

        max_units_duplex: int | None = None
        if duplex_allowed and density_unit == "sf" and density_value > 0 and lot_area > 0:
            max_units_duplex = int(lot_area / density_value)

        duplex_note: str | None = None
        if not duplex_allowed:
            duplex_note = "Not allowed in single-family zones"
        elif sqft_note:
            duplex_note = sqft_note

        building_types.append(BuildingTypeAssessment(
            building_type=BuildingType.DUPLEX,
            allowed=duplex_allowed and not sqft_exceeds,
            constraints=list(base_constraints) if duplex_allowed else [],
            max_units=max_units_duplex,
            max_size_sf=max_buildable_sf if duplex_allowed else None,
            notes=duplex_note,
        ))

        # 6. Calculate setback geometry
        setback_geometry = None
        parcel_geojson = parcel_data.get("geometry")
        setback_front = _get_constraint_value(base_constraints, "setback_front", 20)
        setback_side = _get_constraint_value(base_constraints, "setback_side", 5)
        setback_rear = _get_constraint_value(base_constraints, "setback_rear", 15)

        if parcel_geojson:
            from backend.app.engine.geometry_utils import buffer_inward, parcel_polygon_from_geojson
            try:
                parcel_poly = parcel_polygon_from_geojson(parcel_geojson)
                setback_geometry = buffer_inward(parcel_poly, setback_front, setback_side, setback_rear)
            except Exception:
                setback_geometry = None

        return ResolvedAssessment(
            building_types=building_types,
            setback_geometry=setback_geometry,
            summary_constraints=summary_constraints,
        )


def _get_constraint_value(
    constraints: list[ResolvedConstraint], constraint_type: str, default: float
) -> float:
    for c in constraints:
        if c.constraint_type == constraint_type:
            return c.value
    return default
