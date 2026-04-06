from datetime import datetime, timedelta, timezone

import pytest

from backend.app.engine.adu_preemption import apply_adu_preemption
from backend.app.engine.rule_engine import (
    BASE_ZONE_RULES,
    BMO_RFA_RULES,
    BuildingType,
    Confidence,
    ConstraintResolver,
    ResolvedConstraint,
    _SFH_PARKING_FOOTPRINT_SF,
    _detect_overlay_conflicts,
    _filter_effective_rules,
    _get_bmo_rfa_ratio,
    tag_confidence,
)
from backend.app.engine.zone_parser import ParsedZone


@pytest.fixture
def resolver():
    return ConstraintResolver()


@pytest.fixture
def r1_zone():
    return ParsedZone(zone_class="R1", height_district="1", raw="R1-1")


@pytest.fixture
def r2_zone():
    return ParsedZone(zone_class="R2", height_district="1", raw="R2-1")


@pytest.fixture
def parcel_data():
    return {"lot_area_sf": 7500}


class TestBaseZoneResolution:
    def test_r1_base_zone_only(self, resolver, r1_zone, parcel_data):
        result = resolver.resolve(r1_zone, parcel_data, rule_fragments=[])

        # Check summary constraints match BASE_ZONE_RULES["R1"]
        constraint_map = {c.constraint_type: c for c in result.summary_constraints}
        assert constraint_map["setback_front"].value == 20
        assert constraint_map["setback_side"].value == 5
        assert constraint_map["setback_rear"].value == 15
        assert constraint_map["height_max"].value == 33
        assert constraint_map["min_lot_area"].value == 5000

    def test_all_base_zone_constraints_verified(self, resolver, r1_zone, parcel_data):
        result = resolver.resolve(r1_zone, parcel_data, rule_fragments=[])
        for c in result.summary_constraints:
            assert c.confidence in (Confidence.VERIFIED,), f"{c.constraint_type} not verified"


class TestSpecificPlanMerge:
    def test_most_restrictive_wins(self, resolver, r1_zone, parcel_data):
        """Base zone allows 33' height, specific plan says 28' -> 28' wins."""
        fragments = [{
            "constraint_type": "height_max",
            "value": 28,
            "unit": "ft",
            "zone_applicability": ["R1"],
            "specific_plan": "Test SP",
            "source_document": "Test Specific Plan",
            "overrides_base_zone": False,
            "extraction_reasoning": "AI extracted",
        }]
        result = resolver.resolve(r1_zone, parcel_data, fragments, specific_plan="Test SP")
        height = next(c for c in result.summary_constraints if c.constraint_type == "height_max")
        assert height.value == 28

    def test_override_less_restrictive(self, resolver, r1_zone, parcel_data):
        """With overrides_base_zone=True, specific plan value wins even if less restrictive."""
        fragments = [{
            "constraint_type": "height_max",
            "value": 45,
            "unit": "ft",
            "zone_applicability": ["R1"],
            "specific_plan": "Override SP",
            "source_document": "Override Specific Plan",
            "overrides_base_zone": True,
            "extraction_reasoning": "AI extracted",
        }]
        result = resolver.resolve(r1_zone, parcel_data, fragments, specific_plan="Override SP")
        height = next(c for c in result.summary_constraints if c.constraint_type == "height_max")
        assert height.value == 45


class TestADUPreemption:
    def test_preemption_engages(self):
        """Local side setback 10' -> state law says max 4' -> ADU gets 4'."""
        local = [
            ResolvedConstraint("setback_side", 10, "ft", Confidence.VERIFIED, "LAMC", "base", "base_zone"),
            ResolvedConstraint("setback_rear", 15, "ft", Confidence.VERIFIED, "LAMC", "base", "base_zone"),
            ResolvedConstraint("height_max", 33, "ft", Confidence.VERIFIED, "LAMC", "base", "base_zone"),
        ]
        result = apply_adu_preemption(local)
        side = next(c for c in result.constraints if c.constraint_type == "setback_side")
        rear = next(c for c in result.constraints if c.constraint_type == "setback_rear")
        assert side.value == 4
        assert rear.value == 4
        assert len(result.preemptions_applied) >= 2

    def test_preemption_noop_when_permissive(self):
        """Local side setback 3' (already more permissive) -> stays at 3'."""
        local = [
            ResolvedConstraint("setback_side", 3, "ft", Confidence.VERIFIED, "LAMC", "base", "base_zone"),
            ResolvedConstraint("height_max", 33, "ft", Confidence.VERIFIED, "LAMC", "base", "base_zone"),
        ]
        result = apply_adu_preemption(local)
        side = next(c for c in result.constraints if c.constraint_type == "setback_side")
        assert side.value == 3
        # No preemption on side setback
        side_preemptions = [p for p in result.preemptions_applied if "setback_side" in p]
        assert len(side_preemptions) == 0

    def test_height_preemption_near_transit(self):
        """Local height 16' but near transit -> state floor 18'."""
        local = [
            ResolvedConstraint("height_max", 16, "ft", Confidence.VERIFIED, "LAMC", "base", "base_zone"),
        ]
        result = apply_adu_preemption(local, near_transit=True)
        height = next(c for c in result.constraints if c.constraint_type == "height_max")
        assert height.value == 18

    def test_height_preemption_attached(self):
        """Local height 16' but attached -> state floor 25'."""
        local = [
            ResolvedConstraint("height_max", 16, "ft", Confidence.VERIFIED, "LAMC", "base", "base_zone"),
        ]
        result = apply_adu_preemption(local, attached=True)
        height = next(c for c in result.constraints if c.constraint_type == "height_max")
        assert height.value == 25

    def test_height_noop_when_permissive(self):
        """Local height 45' (already more permissive than 16') -> stays at 45'."""
        local = [
            ResolvedConstraint("height_max", 45, "ft", Confidence.VERIFIED, "LAMC", "base", "base_zone"),
        ]
        result = apply_adu_preemption(local)
        height = next(c for c in result.constraints if c.constraint_type == "height_max")
        assert height.value == 45

    def test_adds_size_constraints(self):
        """ADU preemption adds size_min and size_max_detached if not present."""
        local = [
            ResolvedConstraint("height_max", 33, "ft", Confidence.VERIFIED, "LAMC", "base", "base_zone"),
        ]
        result = apply_adu_preemption(local)
        types = {c.constraint_type for c in result.constraints}
        assert "size_min" in types
        assert "size_max_detached" in types


class TestConfidenceTagging:
    def test_base_zone_verified(self):
        assert tag_confidence("base_zone") == Confidence.VERIFIED

    def test_height_district_verified(self):
        assert tag_confidence("height_district") == Confidence.VERIFIED

    def test_specific_plan_interpreted(self):
        assert tag_confidence("specific_plan", extraction_method="claude") == Confidence.INTERPRETED

    def test_unknown_source(self):
        assert tag_confidence("something_else") == Confidence.UNKNOWN

    def test_specific_plan_without_method_is_unknown(self):
        assert tag_confidence("specific_plan", extraction_method=None) == Confidence.UNKNOWN


class TestProjectParams:
    def test_sqft_caps_adu_max_size(self, resolver, r1_zone, parcel_data):
        result = resolver.resolve(r1_zone, parcel_data, rule_fragments=[], project_params={"sqft": 800})
        adu = next(bt for bt in result.building_types if bt.building_type == BuildingType.ADU)
        assert adu.max_size_sf == 800

    def test_sqft_above_state_max_ignored(self, resolver, r1_zone, parcel_data):
        result = resolver.resolve(r1_zone, parcel_data, rule_fragments=[], project_params={"sqft": 2000})
        adu = next(bt for bt in result.building_types if bt.building_type == BuildingType.ADU)
        assert adu.max_size_sf == 1200

    def test_no_params_default_adu_size(self, resolver, r1_zone, parcel_data):
        result = resolver.resolve(r1_zone, parcel_data, rule_fragments=[])
        adu = next(bt for bt in result.building_types if bt.building_type == BuildingType.ADU)
        assert adu.max_size_sf == 1200

    def test_params_dont_affect_sfh(self, resolver, r1_zone, parcel_data):
        """sqft param caps ADU but not SFH; SFH max_size_sf is RFA-based."""
        result = resolver.resolve(r1_zone, parcel_data, rule_fragments=[], project_params={"sqft": 800})
        sfh = next(bt for bt in result.building_types if bt.building_type == BuildingType.SFH)
        # R1 7500sf lot -> RFA 0.40 (7500 not < 7500 threshold) -> max = 3000
        assert sfh.max_size_sf == 7500 * 0.40


class TestBuildingTypeAllowance:
    def test_sfh_allowed_r1(self, resolver, r1_zone, parcel_data):
        result = resolver.resolve(r1_zone, parcel_data, rule_fragments=[])
        sfh = next(bt for bt in result.building_types if bt.building_type == BuildingType.SFH)
        assert sfh.allowed is True

    def test_duplex_not_allowed_r1(self, resolver, r1_zone, parcel_data):
        result = resolver.resolve(r1_zone, parcel_data, rule_fragments=[])
        duplex = next(bt for bt in result.building_types if bt.building_type == BuildingType.DUPLEX)
        assert duplex.allowed is False

    def test_duplex_allowed_r2(self, resolver, r2_zone, parcel_data):
        result = resolver.resolve(r2_zone, parcel_data, rule_fragments=[])
        duplex = next(bt for bt in result.building_types if bt.building_type == BuildingType.DUPLEX)
        assert duplex.allowed is True

    def test_adu_always_allowed(self, resolver, r1_zone, parcel_data):
        result = resolver.resolve(r1_zone, parcel_data, rule_fragments=[])
        adu = next(bt for bt in result.building_types if bt.building_type == BuildingType.ADU)
        assert adu.allowed is True

    def test_duplex_max_units_r2(self, resolver, r2_zone):
        """R2 density = 1 unit per 2500 sf. 7500 sf lot -> 3 max units."""
        parcel = {"lot_area_sf": 7500}
        result = resolver.resolve(r2_zone, parcel, rule_fragments=[])
        duplex = next(bt for bt in result.building_types if bt.building_type == BuildingType.DUPLEX)
        assert duplex.max_units == 3


class TestEffectiveRuleFiltering:
    def test_superseded_fragment_excluded(self):
        fragments = [
            {"constraint_type": "height_max", "value": 33, "superseded_by": "some-uuid"},
            {"constraint_type": "setback_front", "value": 20},
        ]
        result = _filter_effective_rules(fragments)
        assert len(result) == 1
        assert result[0]["constraint_type"] == "setback_front"

    def test_future_effective_date_excluded(self):
        future = datetime.now(timezone.utc) + timedelta(days=30)
        fragments = [
            {"constraint_type": "height_max", "value": 28, "effective_date": future},
            {"constraint_type": "setback_front", "value": 20},
        ]
        result = _filter_effective_rules(fragments)
        assert len(result) == 1
        assert result[0]["constraint_type"] == "setback_front"

    def test_past_effective_date_included(self):
        past = datetime.now(timezone.utc) - timedelta(days=30)
        fragments = [
            {"constraint_type": "height_max", "value": 28, "effective_date": past},
        ]
        result = _filter_effective_rules(fragments)
        assert len(result) == 1

    def test_no_effective_date_no_superseded_included(self):
        fragments = [
            {"constraint_type": "height_max", "value": 33},
        ]
        result = _filter_effective_rules(fragments)
        assert len(result) == 1

    def test_superseded_with_past_effective_date_still_excluded(self):
        past = datetime.now(timezone.utc) - timedelta(days=30)
        fragments = [
            {"constraint_type": "height_max", "value": 33, "effective_date": past, "superseded_by": "some-uuid"},
        ]
        result = _filter_effective_rules(fragments)
        assert len(result) == 0

    def test_as_of_parameter_deterministic(self):
        fixed_time = datetime(2025, 6, 1, 12, 0, 0)
        fragments = [
            {"constraint_type": "height_max", "value": 28, "effective_date": datetime(2025, 5, 1)},
            {"constraint_type": "setback_front", "value": 20, "effective_date": datetime(2025, 7, 1)},
        ]
        result = _filter_effective_rules(fragments, as_of=fixed_time)
        assert len(result) == 1
        assert result[0]["constraint_type"] == "height_max"


class TestOverlayConflictDetection:
    def test_overlay_less_restrictive_max_flagged(self):
        base = [ResolvedConstraint("height_max", 33, "ft", Confidence.VERIFIED, "LAMC", "base", "base_zone")]
        overlay = [ResolvedConstraint("height_max", 45, "ft", Confidence.INTERPRETED, "SP", "overlay", "specific_plan")]
        conflicts = _detect_overlay_conflicts(base, overlay)
        assert "height_max" in conflicts
        assert "45" in conflicts["height_max"]
        assert "33" in conflicts["height_max"]

    def test_overlay_more_restrictive_max_no_conflict(self):
        base = [ResolvedConstraint("height_max", 33, "ft", Confidence.VERIFIED, "LAMC", "base", "base_zone")]
        overlay = [ResolvedConstraint("height_max", 28, "ft", Confidence.INTERPRETED, "SP", "overlay", "specific_plan")]
        conflicts = _detect_overlay_conflicts(base, overlay)
        assert "height_max" not in conflicts

    def test_overlay_less_restrictive_min_flagged(self):
        base = [ResolvedConstraint("setback_front", 20, "ft", Confidence.VERIFIED, "LAMC", "base", "base_zone")]
        overlay = [ResolvedConstraint("setback_front", 15, "ft", Confidence.INTERPRETED, "SP", "overlay", "specific_plan")]
        conflicts = _detect_overlay_conflicts(base, overlay)
        assert "setback_front" in conflicts

    def test_overlay_more_restrictive_min_no_conflict(self):
        base = [ResolvedConstraint("setback_front", 20, "ft", Confidence.VERIFIED, "LAMC", "base", "base_zone")]
        overlay = [ResolvedConstraint("setback_front", 25, "ft", Confidence.INTERPRETED, "SP", "overlay", "specific_plan")]
        conflicts = _detect_overlay_conflicts(base, overlay)
        assert "setback_front" not in conflicts

    def test_non_dimensional_constraint_no_conflict(self):
        base = [ResolvedConstraint("density", 1, "unit/lot", Confidence.VERIFIED, "LAMC", "base", "base_zone")]
        overlay = [ResolvedConstraint("density", 5, "unit/lot", Confidence.INTERPRETED, "SP", "overlay", "specific_plan")]
        conflicts = _detect_overlay_conflicts(base, overlay)
        assert "density" not in conflicts

    def test_overlay_constraint_not_in_base_no_conflict(self):
        base = [ResolvedConstraint("height_max", 33, "ft", Confidence.VERIFIED, "LAMC", "base", "base_zone")]
        overlay = [ResolvedConstraint("far_max", 3.0, "ratio", Confidence.INTERPRETED, "SP", "overlay", "specific_plan")]
        conflicts = _detect_overlay_conflicts(base, overlay)
        assert len(conflicts) == 0


class TestVarianceAndConflictNotes:
    @pytest.fixture
    def resolver(self):
        return ConstraintResolver()

    @pytest.fixture
    def r1_zone(self):
        return ParsedZone(zone_class="R1", height_district="1", raw="R1-1")

    @pytest.fixture
    def parcel_data(self):
        return {"lot_area_sf": 7500}

    def test_conflict_notes_on_less_restrictive_overlay(self, resolver, r1_zone, parcel_data):
        """Base zone height_max=33', overlay says 45' (less restrictive) -> conflict noted, value stays 33'."""
        fragments = [{
            "constraint_type": "height_max",
            "value": 45,
            "unit": "ft",
            "zone_applicability": ["R1"],
            "source_document": "Hillside Overlay",
            "extraction_reasoning": "AI extracted",
        }]
        result = resolver.resolve(r1_zone, parcel_data, fragments)
        height = next(c for c in result.summary_constraints if c.constraint_type == "height_max")
        assert height.value == 33
        assert height.conflict_notes is not None
        assert "45" in height.conflict_notes

    def test_no_conflict_notes_on_more_restrictive_overlay(self, resolver, r1_zone, parcel_data):
        """Base zone height_max=33', overlay says 28' (more restrictive) -> no conflict, value is 28'."""
        fragments = [{
            "constraint_type": "height_max",
            "value": 28,
            "unit": "ft",
            "zone_applicability": ["R1"],
            "source_document": "Hillside Overlay",
            "extraction_reasoning": "AI extracted",
        }]
        result = resolver.resolve(r1_zone, parcel_data, fragments)
        height = next(c for c in result.summary_constraints if c.constraint_type == "height_max")
        assert height.value == 28
        assert height.conflict_notes is None

    def test_setback_conflict_notes(self, resolver, r1_zone, parcel_data):
        """Base setback_front=20', overlay says 15' (less restrictive for min) -> conflict noted, value stays 20'."""
        fragments = [{
            "constraint_type": "setback_front",
            "value": 15,
            "unit": "ft",
            "zone_applicability": ["R1"],
            "source_document": "Test Overlay",
            "extraction_reasoning": "AI extracted",
        }]
        result = resolver.resolve(r1_zone, parcel_data, fragments)
        setback = next(c for c in result.summary_constraints if c.constraint_type == "setback_front")
        assert setback.value == 20
        assert setback.conflict_notes is not None

    def test_variance_available_true_by_default(self, resolver, r1_zone, parcel_data):
        result = resolver.resolve(r1_zone, parcel_data, rule_fragments=[])
        for c in result.summary_constraints:
            assert c.variance_available is True

    def test_variance_false_propagated_from_fragment(self, resolver, r1_zone, parcel_data):
        fragments = [{
            "constraint_type": "height_max",
            "value": 28,
            "unit": "ft",
            "zone_applicability": ["R1"],
            "source_document": "Restrictive Overlay",
            "extraction_reasoning": "AI extracted",
            "variance_available": False,
        }]
        result = resolver.resolve(r1_zone, parcel_data, fragments)
        height = next(c for c in result.summary_constraints if c.constraint_type == "height_max")
        assert height.value == 28
        assert height.variance_available is False

    def test_variance_and_on_merge(self, resolver, r1_zone, parcel_data):
        """Base variance=True, fragment variance=False -> merged result is False."""
        fragments = [{
            "constraint_type": "height_max",
            "value": 45,
            "unit": "ft",
            "zone_applicability": ["R1"],
            "source_document": "Test SP",
            "extraction_reasoning": "AI extracted",
            "variance_available": False,
        }]
        result = resolver.resolve(r1_zone, parcel_data, fragments)
        height = next(c for c in result.summary_constraints if c.constraint_type == "height_max")
        # Base (33') wins as most restrictive, but variance_available is ANDed -> False
        assert height.value == 33
        assert height.variance_available is False

    def test_superseded_fragment_excluded_in_resolve(self, resolver, r1_zone, parcel_data):
        fragments = [{
            "constraint_type": "height_max",
            "value": 28,
            "unit": "ft",
            "zone_applicability": ["R1"],
            "source_document": "Old rule",
            "extraction_reasoning": "AI extracted",
            "superseded_by": "some-uuid",
        }]
        result = resolver.resolve(r1_zone, parcel_data, fragments)
        height = next(c for c in result.summary_constraints if c.constraint_type == "height_max")
        assert height.value == 33  # base zone value, superseded fragment excluded

    def test_future_fragment_excluded_in_resolve(self, resolver, r1_zone, parcel_data):
        future = datetime.now(timezone.utc) + timedelta(days=365)
        fragments = [{
            "constraint_type": "height_max",
            "value": 28,
            "unit": "ft",
            "zone_applicability": ["R1"],
            "source_document": "Future rule",
            "extraction_reasoning": "AI extracted",
            "effective_date": future,
        }]
        result = resolver.resolve(r1_zone, parcel_data, fragments)
        height = next(c for c in result.summary_constraints if c.constraint_type == "height_max")
        assert height.value == 33  # base zone value, future fragment excluded


class TestADUVarianceDisabled:
    def test_preempted_setback_variance_false(self):
        """Local side setback 10' preempted to 4' -> variance_available=False."""
        local = [
            ResolvedConstraint("setback_side", 10, "ft", Confidence.VERIFIED, "LAMC", "base", "base_zone"),
        ]
        result = apply_adu_preemption(local)
        side = next(c for c in result.constraints if c.constraint_type == "setback_side")
        assert side.value == 4
        assert side.variance_available is False

    def test_non_preempted_preserves_variance(self):
        """Local height 45' not preempted -> preserves incoming variance_available."""
        local = [
            ResolvedConstraint("height_max", 45, "ft", Confidence.VERIFIED, "LAMC", "base", "base_zone", variance_available=True),
        ]
        result = apply_adu_preemption(local)
        height = next(c for c in result.constraints if c.constraint_type == "height_max")
        assert height.value == 45
        assert height.variance_available is True

    def test_non_preempted_preserves_variance_false(self):
        """If incoming variance_available=False and not preempted, it stays False."""
        local = [
            ResolvedConstraint("height_max", 45, "ft", Confidence.VERIFIED, "LAMC", "base", "base_zone", variance_available=False),
        ]
        result = apply_adu_preemption(local)
        height = next(c for c in result.constraints if c.constraint_type == "height_max")
        assert height.variance_available is False

    def test_preempted_height_variance_false(self):
        """Local height 16' preempted to state floor -> variance_available=False."""
        local = [
            ResolvedConstraint("height_max", 16, "ft", Confidence.VERIFIED, "LAMC", "base", "base_zone"),
        ]
        result = apply_adu_preemption(local)
        height = next(c for c in result.constraints if c.constraint_type == "height_max")
        assert height.value == 16  # 16 >= 16 so not preempted
        assert height.variance_available is True

    def test_preempted_height_below_floor_variance_false(self):
        """Local height 14' preempted to 16' -> variance_available=False."""
        local = [
            ResolvedConstraint("height_max", 14, "ft", Confidence.VERIFIED, "LAMC", "base", "base_zone"),
        ]
        result = apply_adu_preemption(local)
        height = next(c for c in result.constraints if c.constraint_type == "height_max")
        assert height.value == 16
        assert height.variance_available is False

    def test_guaranteed_size_min_variance_false(self):
        """size_min injected by ADU preemption has variance_available=False."""
        local = [
            ResolvedConstraint("height_max", 33, "ft", Confidence.VERIFIED, "LAMC", "base", "base_zone"),
        ]
        result = apply_adu_preemption(local)
        size_min = next(c for c in result.constraints if c.constraint_type == "size_min")
        assert size_min.variance_available is False

    def test_guaranteed_size_max_detached_variance_false(self):
        """size_max_detached injected by ADU preemption has variance_available=False."""
        local = [
            ResolvedConstraint("height_max", 33, "ft", Confidence.VERIFIED, "LAMC", "base", "base_zone"),
        ]
        result = apply_adu_preemption(local)
        size_max = next(c for c in result.constraints if c.constraint_type == "size_max_detached")
        assert size_max.variance_available is False


class TestBedroomBathroomValidation:
    """Tests for bedroom/bathroom min sqft validation and parking footprint deduction."""

    @pytest.fixture
    def resolver(self):
        return ConstraintResolver()

    @pytest.fixture
    def r1_zone(self):
        return ParsedZone(zone_class="R1", height_district="1", raw="R1-1")

    @pytest.fixture
    def r2_zone(self):
        return ParsedZone(zone_class="R2", height_district="1", raw="R2-1")

    def test_min_sqft_warning_when_undersized(self, resolver, r1_zone):
        """4 bed / 3 bath with 800 sqft -> SFH notes contain 'undersized'."""
        # min_sqft = 4*120 + 3*40 + 200 = 480+120+200 = 800, so 800 is not < 800.
        # Use 799 to be truly undersized.
        parcel = {"lot_area_sf": 7500}
        params = {"bedrooms": 4, "bathrooms": 3, "sqft": 799}
        result = resolver.resolve(r1_zone, parcel, rule_fragments=[], project_params=params)
        sfh = next(bt for bt in result.building_types if bt.building_type == BuildingType.SFH)
        assert sfh.notes is not None
        assert "undersized" in sfh.notes

    def test_no_warning_when_adequate_sqft(self, resolver, r1_zone):
        """3 bed / 2 bath with 2000 sqft -> SFH notes do NOT contain 'undersized'."""
        parcel = {"lot_area_sf": 7500}
        params = {"bedrooms": 3, "bathrooms": 2, "sqft": 2000}
        result = resolver.resolve(r1_zone, parcel, rule_fragments=[], project_params=params)
        sfh = next(bt for bt in result.building_types if bt.building_type == BuildingType.SFH)
        if sfh.notes:
            assert "undersized" not in sfh.notes

    def test_bedrooms_trigger_far_check_without_sqft(self, resolver):
        """5 bed / 4 bath (min_sqft=960) on small lot with RFA -> SFH not allowed if 960 > max_buildable."""
        # R2 uses BMO RFA 0.45 for SFH. lot_area=400sf -> max_buildable=400*0.45=180
        # min_sqft = 5*120 + 4*40 + 200 = 600+160+200 = 960 > 180 -> exceeds
        r2_zone = ParsedZone(zone_class="R2", height_district="1", raw="R2-1")
        parcel = {"lot_area_sf": 400}
        params = {"bedrooms": 5, "bathrooms": 4}  # no sqft
        result = resolver.resolve(r2_zone, parcel, rule_fragments=[], project_params=params)
        sfh = next(bt for bt in result.building_types if bt.building_type == BuildingType.SFH)
        assert sfh.allowed is False

    def test_parking_deduction_affects_duplex(self, resolver):
        """Duplex uses HD FAR with parking deduction; SFH uses RFA without parking deduction."""
        # R2-1: far_max=3.0 from HD1. lot_area=500 -> duplex_max_buildable=1500,
        # duplex_max_livable=1500-400=1100. proposed_sqft=1200 > 1100 -> Duplex not allowed
        r2_zone = ParsedZone(zone_class="R2", height_district="1", raw="R2-1")
        parcel = {"lot_area_sf": 500}
        params = {"sqft": 1200}
        result = resolver.resolve(r2_zone, parcel, rule_fragments=[], project_params=params)
        duplex = next(bt for bt in result.building_types if bt.building_type == BuildingType.DUPLEX)
        assert duplex.allowed is False
        assert duplex.notes is not None
        assert "parking" in duplex.notes.lower()
        # max_size_sf reports the total envelope (not livable)
        assert duplex.max_size_sf == 1500

    def test_no_parking_deduction_for_adu(self, resolver):
        """Same lot, ADU is still allowed (parking waived under SB 13)."""
        r2_zone = ParsedZone(zone_class="R2", height_district="1", raw="R2-1")
        parcel = {"lot_area_sf": 500}
        params = {"sqft": 1200}
        result = resolver.resolve(r2_zone, parcel, rule_fragments=[], project_params=params)
        adu = next(bt for bt in result.building_types if bt.building_type == BuildingType.ADU)
        assert adu.allowed is True

    def test_no_validation_without_params(self, resolver, r1_zone):
        """No bedrooms/bathrooms/sqft -> no notes on SFH."""
        parcel = {"lot_area_sf": 7500}
        result = resolver.resolve(r1_zone, parcel, rule_fragments=[])
        sfh = next(bt for bt in result.building_types if bt.building_type == BuildingType.SFH)
        assert sfh.notes is None


class TestBMORFA:
    """Tests for BMO Residential Floor Area logic: tiering, per-building-type differentiation,
    and parking deduction conditional behavior."""

    @pytest.fixture
    def resolver(self):
        return ConstraintResolver()

    def test_bmo_rfa_tier_r1(self, resolver):
        """R1 zone: 5000sf lot -> RFA 0.45 -> max 2250; 8000sf lot -> RFA 0.40 -> max 3200."""
        r1 = ParsedZone(zone_class="R1", height_district="1", raw="R1-1")

        # Small lot: 5000 < 7500 threshold -> 0.45
        result_small = resolver.resolve(r1, {"lot_area_sf": 5000}, rule_fragments=[])
        sfh_small = next(bt for bt in result_small.building_types if bt.building_type == BuildingType.SFH)
        assert sfh_small.max_size_sf == 2250

        # Large lot: 8000 >= 7500 threshold -> 0.40
        result_large = resolver.resolve(r1, {"lot_area_sf": 8000}, rule_fragments=[])
        sfh_large = next(bt for bt in result_large.building_types if bt.building_type == BuildingType.SFH)
        assert sfh_large.max_size_sf == 3200

    def test_sfh_vs_duplex_r3_far(self, resolver):
        """R3-1 zone, 5000sf lot: SFH uses RFA (0.45 -> 2250), Duplex uses HD FAR (3.0 -> 15000)."""
        r3 = ParsedZone(zone_class="R3", height_district="1", raw="R3-1")
        parcel = {"lot_area_sf": 5000}
        result = resolver.resolve(r3, parcel, rule_fragments=[])

        sfh = next(bt for bt in result.building_types if bt.building_type == BuildingType.SFH)
        assert sfh.max_size_sf == 2250  # 5000 * 0.45 RFA

        duplex = next(bt for bt in result.building_types if bt.building_type == BuildingType.DUPLEX)
        assert duplex.max_size_sf == 15000  # 5000 * 3.0 HD FAR

    def test_no_parking_deduction_on_rfa(self, resolver):
        """SFH max_size_sf = lot_area * RFA exactly — no 400sf parking deduction."""
        r1 = ParsedZone(zone_class="R1", height_district="1", raw="R1-1")
        parcel = {"lot_area_sf": 6000}
        result = resolver.resolve(r1, parcel, rule_fragments=[])
        sfh = next(bt for bt in result.building_types if bt.building_type == BuildingType.SFH)
        # 6000 < 7500 -> RFA 0.45 -> 2700 exactly, no parking subtracted
        expected = 6000 * 0.45
        assert sfh.max_size_sf == expected

    def test_far_max_in_sfh_constraints(self, resolver):
        """SFH constraints list contains far_max with RFA value, not HD FAR."""
        r1 = ParsedZone(zone_class="R1", height_district="1", raw="R1-1")
        parcel = {"lot_area_sf": 5000}
        result = resolver.resolve(r1, parcel, rule_fragments=[])
        sfh = next(bt for bt in result.building_types if bt.building_type == BuildingType.SFH)
        far_constraint = next(c for c in sfh.constraints if c.constraint_type == "far_max")
        assert far_constraint.value == 0.45
        assert "BMO" in far_constraint.citation


class TestMaxBedrooms:

    @pytest.fixture
    def resolver(self):
        return ConstraintResolver()

    def test_sfh_max_bedrooms_r1_small_lot(self, resolver):
        """R1-1, 5000 sf lot: RFA 0.45 -> max_livable 2250. (2250 - 200) / 70 = 29."""
        r1 = ParsedZone(zone_class="R1", height_district="1", raw="R1-1")
        result = resolver.resolve(r1, {"lot_area_sf": 5000}, rule_fragments=[])
        sfh = next(bt for bt in result.building_types if bt.building_type == BuildingType.SFH)
        assert sfh.max_bedrooms == 29

    def test_sfh_max_bedrooms_r1_large_lot(self, resolver):
        """R1-1, 7500 sf lot: RFA 0.40 -> max_livable 3000. (3000 - 200) / 70 = 40."""
        r1 = ParsedZone(zone_class="R1", height_district="1", raw="R1-1")
        result = resolver.resolve(r1, {"lot_area_sf": 7500}, rule_fragments=[])
        sfh = next(bt for bt in result.building_types if bt.building_type == BuildingType.SFH)
        assert sfh.max_bedrooms == 40

    def test_adu_max_bedrooms(self, resolver):
        """Any zone: ADU max_size 1200. (1200 - 400) / 70 = 11."""
        r1 = ParsedZone(zone_class="R1", height_district="1", raw="R1-1")
        result = resolver.resolve(r1, {"lot_area_sf": 7500}, rule_fragments=[])
        adu = next(bt for bt in result.building_types if bt.building_type == BuildingType.ADU)
        assert adu.max_bedrooms == 11

    def test_guest_house_matches_sfh(self, resolver):
        """Guest House shares SFH's RFA -> same max_bedrooms."""
        r1 = ParsedZone(zone_class="R1", height_district="1", raw="R1-1")
        result = resolver.resolve(r1, {"lot_area_sf": 7500}, rule_fragments=[])
        sfh = next(bt for bt in result.building_types if bt.building_type == BuildingType.SFH)
        gh = next(bt for bt in result.building_types if bt.building_type == BuildingType.GUEST_HOUSE)
        assert gh.max_bedrooms == sfh.max_bedrooms

    def test_duplex_max_bedrooms_r2(self, resolver):
        """R2-1, 7500 sf: FAR 3.0 -> buildable 22500, livable 22100. (22100 - 200) / 70 = 312."""
        r2 = ParsedZone(zone_class="R2", height_district="1", raw="R2-1")
        result = resolver.resolve(r2, {"lot_area_sf": 7500}, rule_fragments=[])
        duplex = next(bt for bt in result.building_types if bt.building_type == BuildingType.DUPLEX)
        assert duplex.max_bedrooms == 312

    def test_duplex_max_bedrooms_not_allowed(self, resolver):
        """R1-1: Duplex not allowed -> max_bedrooms is None."""
        r1 = ParsedZone(zone_class="R1", height_district="1", raw="R1-1")
        result = resolver.resolve(r1, {"lot_area_sf": 7500}, rule_fragments=[])
        duplex = next(bt for bt in result.building_types if bt.building_type == BuildingType.DUPLEX)
        assert duplex.max_bedrooms is None

    def test_max_bedrooms_none_when_no_area(self, resolver):
        """lot_area=0 -> SFH max_bedrooms is None."""
        r1 = ParsedZone(zone_class="R1", height_district="1", raw="R1-1")
        result = resolver.resolve(r1, {"lot_area_sf": 0}, rule_fragments=[])
        sfh = next(bt for bt in result.building_types if bt.building_type == BuildingType.SFH)
        assert sfh.max_bedrooms is None


class TestPerConstraintOverride:
    @pytest.fixture
    def resolver(self):
        return ConstraintResolver()

    @pytest.fixture
    def r1_zone(self):
        return ParsedZone(zone_class="R1", height_district="1", raw="R1-1")

    @pytest.fixture
    def parcel_data(self):
        return {"lot_area_sf": 7500}

    def test_override_only_affects_marked_type(self, resolver, r1_zone, parcel_data):
        """height_max overrides (45 > base 33), but setback_front uses most-restrictive-wins (base 20 > 15)."""
        fragments = [
            {
                "constraint_type": "height_max",
                "value": 45,
                "unit": "ft",
                "zone_applicability": ["R1"],
                "specific_plan": "Mixed SP",
                "source_document": "Mixed Specific Plan",
                "overrides_base_zone": True,
                "extraction_reasoning": "AI extracted",
            },
            {
                "constraint_type": "setback_front",
                "value": 15,
                "unit": "ft",
                "zone_applicability": ["R1"],
                "specific_plan": "Mixed SP",
                "source_document": "Mixed Specific Plan",
                "overrides_base_zone": False,
                "extraction_reasoning": "AI extracted",
            },
        ]
        result = resolver.resolve(r1_zone, parcel_data, fragments, specific_plan="Mixed SP")
        cmap = {c.constraint_type: c for c in result.summary_constraints}
        assert cmap["height_max"].value == 45  # override wins
        assert cmap["setback_front"].value == 20  # most-restrictive-wins preserves base

    def test_override_multiple_types(self, resolver, r1_zone, parcel_data):
        """Two different constraint types both with overrides_base_zone=True override independently."""
        fragments = [
            {
                "constraint_type": "height_max",
                "value": 45,
                "unit": "ft",
                "zone_applicability": ["R1"],
                "specific_plan": "Multi SP",
                "source_document": "Multi Specific Plan",
                "overrides_base_zone": True,
                "extraction_reasoning": "AI extracted",
            },
            {
                "constraint_type": "setback_front",
                "value": 15,
                "unit": "ft",
                "zone_applicability": ["R1"],
                "specific_plan": "Multi SP",
                "source_document": "Multi Specific Plan",
                "overrides_base_zone": True,
                "extraction_reasoning": "AI extracted",
            },
        ]
        result = resolver.resolve(r1_zone, parcel_data, fragments, specific_plan="Multi SP")
        cmap = {c.constraint_type: c for c in result.summary_constraints}
        assert cmap["height_max"].value == 45  # override wins
        assert cmap["setback_front"].value == 15  # override wins

    def test_no_overrides_preserves_behavior(self, resolver, r1_zone, parcel_data):
        """All fragments overrides_base_zone=False -> most-restrictive-wins for all."""
        fragments = [
            {
                "constraint_type": "height_max",
                "value": 45,
                "unit": "ft",
                "zone_applicability": ["R1"],
                "specific_plan": "No Override SP",
                "source_document": "No Override Plan",
                "overrides_base_zone": False,
                "extraction_reasoning": "AI extracted",
            },
            {
                "constraint_type": "setback_front",
                "value": 15,
                "unit": "ft",
                "zone_applicability": ["R1"],
                "specific_plan": "No Override SP",
                "source_document": "No Override Plan",
                "overrides_base_zone": False,
                "extraction_reasoning": "AI extracted",
            },
        ]
        result = resolver.resolve(r1_zone, parcel_data, fragments, specific_plan="No Override SP")
        cmap = {c.constraint_type: c for c in result.summary_constraints}
        assert cmap["height_max"].value == 33  # base wins (more restrictive)
        assert cmap["setback_front"].value == 20  # base wins (more restrictive)
