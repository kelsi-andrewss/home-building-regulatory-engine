import pytest

from backend.app.engine.adu_preemption import apply_adu_preemption
from backend.app.engine.rule_engine import (
    BASE_ZONE_RULES,
    BuildingType,
    Confidence,
    ConstraintResolver,
    ResolvedConstraint,
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
        result = resolver.resolve(r1_zone, parcel_data, rule_fragments=[], project_params={"sqft": 800})
        sfh = next(bt for bt in result.building_types if bt.building_type == BuildingType.SFH)
        assert sfh.max_size_sf is None


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
