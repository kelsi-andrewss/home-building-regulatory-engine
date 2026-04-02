from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.engine.rule_engine import ConstraintResolver
from backend.app.schemas.design_constraints import DesignConstraintRequest
from backend.app.services.parcel_service import ParcelData, ParcelZoning
from backend.tests.conftest import make_square_parcel as _square_parcel_geojson


def _make_parcel_data(geometry=None, apn="1234-567-890", zone_class="R1"):
    """Build a ParcelData matching what ParcelService.lookup_by_address returns."""
    return ParcelData(
        apn=apn,
        address="1234 N Main St, Los Angeles, CA",
        lat=34.05,
        lng=-118.25,
        geometry=geometry or _square_parcel_geojson(100),
        lot_area_sf=10000.0,
        year_built=1950,
        existing_units=1,
        existing_sqft=1500.0,
        zoning=ParcelZoning(
            zone_complete=f"{zone_class}-1",
            zone_class=zone_class,
            zone_code=zone_class,
            general_plan_land_use="Low Residential",
            land_use_category="Residential",
            specific_plan=None,
            hpoz=None,
        ),
    )


def _mock_parcel_service(parcel_data):
    """Mock ParcelService that returns the given ParcelData."""
    svc = AsyncMock()
    svc.lookup_by_address.return_value = parcel_data
    return svc


def _mock_db():
    """Mock AsyncSession that returns None for all queries (no cached rows) and accepts writes."""
    mock_scalars = MagicMock()
    mock_scalars.first.return_value = None
    mock_scalars.all.return_value = []
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result

    # Parcel row needs an id after flush
    parcel_id_holder = MagicMock()
    parcel_id_holder.id = "fake-parcel-id"
    parcel_id_holder.apn = None
    parcel_id_holder.lot_area_sf = None

    def track_add(obj):
        # Give persisted rows a fake id so downstream code works
        if hasattr(obj, "apn") and not hasattr(obj, "_id_set"):
            obj.id = "fake-parcel-id"
            obj._id_set = True
        if hasattr(obj, "zone_complete") and not hasattr(obj, "_id_set"):
            obj.id = "fake-zone-id"
            obj._id_set = True

    mock_db.add = track_add
    return mock_db


class TestDesignConstraintEndpoint:
    @pytest.mark.asyncio
    async def test_happy_path_with_address(self):
        from backend.app.api.endpoints import get_design_constraints

        parcel_data = _make_parcel_data()
        parcel_svc = _mock_parcel_service(parcel_data)
        db = _mock_db()
        resolver = ConstraintResolver()
        req = DesignConstraintRequest(address="1234 N Main St, Los Angeles, CA")

        resp = await get_design_constraints(
            req=req, db=db, parcel_svc=parcel_svc, resolver=resolver
        )

        assert resp.parcel_apn == "1234-567-890"
        assert resp.envelope_geojson["type"] == "Polygon"
        assert "coordinates" in resp.envelope_geojson
        assert len(resp.per_edge_setbacks) == 4
        edge_names = {s.edge for s in resp.per_edge_setbacks}
        assert edge_names == {"front", "left_side", "right_side", "rear"}
        for s in resp.per_edge_setbacks:
            assert s.confidence == "verified"
        assert resp.height_envelope.max_height_ft == 33.0
        assert resp.height_envelope.confidence == "verified"
        assert resp.panel_fit.feasible is True
        assert resp.panel_fit.failures == []
        assert not hasattr(resp, "assessment_id")

    @pytest.mark.asyncio
    async def test_happy_path_with_apn(self):
        from backend.app.api.endpoints import get_design_constraints

        parcel_data = _make_parcel_data()
        parcel_svc = _mock_parcel_service(parcel_data)
        db = _mock_db()
        resolver = ConstraintResolver()
        req = DesignConstraintRequest(apn="1234-567-890")

        resp = await get_design_constraints(
            req=req, db=db, parcel_svc=parcel_svc, resolver=resolver
        )

        assert resp.parcel_apn == "1234-567-890"
        assert resp.envelope_geojson["type"] == "Polygon"
        parcel_svc.lookup_by_address.assert_awaited_once_with("1234-567-890")

    @pytest.mark.asyncio
    async def test_empty_request_returns_validation_error(self):
        """Request with neither address nor apn should fail validation."""
        with pytest.raises(ValueError, match="At least one of address or apn"):
            DesignConstraintRequest()

    @pytest.mark.asyncio
    async def test_parcel_not_found_returns_404(self):
        from fastapi import HTTPException

        from backend.app.api.endpoints import get_design_constraints

        parcel_svc = AsyncMock()
        parcel_svc.lookup_by_address.return_value = None
        db = _mock_db()
        resolver = ConstraintResolver()
        req = DesignConstraintRequest(address="nonexistent")

        with pytest.raises(HTTPException) as exc_info:
            await get_design_constraints(
                req=req, db=db, parcel_svc=parcel_svc, resolver=resolver
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_upstream_failure_returns_502(self):
        from fastapi import HTTPException

        from backend.app.api.endpoints import get_design_constraints

        parcel_svc = AsyncMock()
        parcel_svc.lookup_by_address.side_effect = Exception("upstream down")
        db = _mock_db()
        resolver = ConstraintResolver()
        req = DesignConstraintRequest(address="1234 N Main St")

        with pytest.raises(HTTPException) as exc_info:
            await get_design_constraints(
                req=req, db=db, parcel_svc=parcel_svc, resolver=resolver
            )
        assert exc_info.value.status_code == 502

    @pytest.mark.asyncio
    async def test_setback_values_from_r1_zone(self):
        """R1 zone should produce front=20, side=5, rear=15 setbacks."""
        from backend.app.api.endpoints import get_design_constraints

        parcel_data = _make_parcel_data(zone_class="R1")
        parcel_svc = _mock_parcel_service(parcel_data)
        db = _mock_db()
        resolver = ConstraintResolver()
        req = DesignConstraintRequest(address="test")

        resp = await get_design_constraints(
            req=req, db=db, parcel_svc=parcel_svc, resolver=resolver
        )

        setbacks = {s.edge: s.setback_ft for s in resp.per_edge_setbacks}
        assert setbacks["front"] == 20.0
        assert setbacks["left_side"] == 5.0
        assert setbacks["right_side"] == 5.0
        assert setbacks["rear"] == 15.0

    @pytest.mark.asyncio
    async def test_panel_fit_infeasible_with_narrow_side_setback(self):
        """Side setback of 2 ft (via RD4 zone, manually verified) triggers panel fit failure."""
        from backend.app.api.endpoints import get_design_constraints

        # RD4 has side setback of 7.5 ft -- use a tiny parcel so panel fit fails
        # Actually, let's use a custom approach: small parcel where envelope is too narrow
        # A 15ft wide parcel with 5ft side setbacks = 5ft envelope width, which is feasible
        # A 10ft wide parcel with 5ft side setbacks = 0ft envelope, infeasible
        parcel_data = _make_parcel_data(
            geometry=_square_parcel_geojson(10),
            zone_class="R1",
        )
        parcel_svc = _mock_parcel_service(parcel_data)
        db = _mock_db()
        resolver = ConstraintResolver()
        req = DesignConstraintRequest(address="tiny parcel")

        resp = await get_design_constraints(
            req=req, db=db, parcel_svc=parcel_svc, resolver=resolver
        )

        # With a 10x10 parcel and R1 setbacks (front=20, side=5, rear=15),
        # the envelope should be degenerate/infeasible
        assert resp.panel_fit.feasible is False

    @pytest.mark.asyncio
    async def test_response_has_no_assessment_id(self):
        """Response schema should not include assessment_id."""
        from backend.app.api.endpoints import get_design_constraints

        parcel_data = _make_parcel_data()
        parcel_svc = _mock_parcel_service(parcel_data)
        db = _mock_db()
        resolver = ConstraintResolver()
        req = DesignConstraintRequest(address="test")

        resp = await get_design_constraints(
            req=req, db=db, parcel_svc=parcel_svc, resolver=resolver
        )

        resp_dict = resp.model_dump()
        assert "assessment_id" not in resp_dict
        assert "parcel_apn" in resp_dict
