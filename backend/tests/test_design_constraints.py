import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.api.endpoints import _extract_constraint_from_result
from backend.tests.conftest import make_square_parcel as _square_parcel_geojson


def _mock_assessment_result(
    setback_front=20, setback_side=5, setback_rear=15, height_max=33
):
    """Return a dict matching Assessment.result format."""
    return {
        "building_types": [
            {
                "type": "SFH",
                "allowed": True,
                "confidence": "verified",
                "constraints": [
                    {
                        "name": "setback_front",
                        "value": f"{setback_front} ft",
                        "confidence": "verified",
                        "citation": "LAMC SS12.08",
                        "explanation": "Base zone R1 setback_front",
                    },
                    {
                        "name": "setback_side",
                        "value": f"{setback_side} ft",
                        "confidence": "verified",
                        "citation": "LAMC SS12.08",
                        "explanation": "Base zone R1 setback_side",
                    },
                    {
                        "name": "setback_rear",
                        "value": f"{setback_rear} ft",
                        "confidence": "verified",
                        "citation": "LAMC SS12.08",
                        "explanation": "Base zone R1 setback_rear",
                    },
                    {
                        "name": "height_max",
                        "value": f"{height_max} ft",
                        "confidence": "verified",
                        "citation": "LAMC SS12.08",
                        "explanation": "Base zone R1 height_max",
                    },
                ],
                "max_buildable_area_sf": None,
                "max_units": 1,
            }
        ],
        "setback_geometry": None,
    }


class TestExtractConstraintFromResult:
    def test_extracts_known_constraint(self):
        constraints = [
            {
                "name": "setback_front",
                "value": "20 ft",
                "confidence": "verified",
                "citation": "LAMC SS12.08",
                "explanation": "test",
            }
        ]
        val, conf, cite = _extract_constraint_from_result(constraints, "setback_front", 99.0)
        assert val == 20.0
        assert conf == "verified"
        assert cite == "LAMC SS12.08"

    def test_missing_constraint_returns_default(self):
        val, conf, cite = _extract_constraint_from_result([], "setback_front", 99.0)
        assert val == 99.0
        assert conf == "unknown"
        assert cite == ""

    def test_malformed_value_returns_default(self):
        constraints = [
            {
                "name": "setback_front",
                "value": "unknown",
                "confidence": "unknown",
                "citation": "",
                "explanation": "",
            }
        ]
        val, conf, cite = _extract_constraint_from_result(constraints, "setback_front", 99.0)
        assert val == 99.0
        assert conf == "unknown"
        assert cite == ""

    def test_value_with_no_space(self):
        constraints = [
            {
                "name": "height_max",
                "value": "33",
                "confidence": "verified",
                "citation": "LAMC",
                "explanation": "",
            }
        ]
        val, conf, cite = _extract_constraint_from_result(constraints, "height_max", 0.0)
        assert val == 33.0
        assert conf == "verified"

    def test_float_value(self):
        constraints = [
            {
                "name": "setback_side",
                "value": "7.5 ft",
                "confidence": "interpreted",
                "citation": "SP",
                "explanation": "",
            }
        ]
        val, conf, cite = _extract_constraint_from_result(constraints, "setback_side", 5.0)
        assert val == 7.5
        assert conf == "interpreted"


def _make_mock_assessment(assessment_id, result, parcel_geojson=None):
    """Build mock Assessment with linked Parcel and Zone."""
    mock_parcel = MagicMock()
    mock_parcel.apn = "1234-567-890"
    mock_parcel.raw_api_response = {"geometry": parcel_geojson} if parcel_geojson else {}

    mock_zone = MagicMock()
    mock_zone.zone_complete = "R1-1"

    mock_assessment = MagicMock()
    mock_assessment.id = assessment_id
    mock_assessment.parcel = mock_parcel
    mock_assessment.zone = mock_zone
    mock_assessment.result = result

    return mock_assessment


def _mock_db_returning(assessment):
    """Build an AsyncMock db session that returns the given assessment."""
    mock_scalars = MagicMock()
    mock_scalars.first.return_value = assessment
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result
    return mock_db


class TestDesignConstraintEndpoint:
    @pytest.fixture
    def assessment_id(self):
        return uuid.uuid4()

    @pytest.mark.asyncio
    async def test_happy_path_returns_all_fields(self, assessment_id):
        from backend.app.api.endpoints import get_design_constraints

        parcel_geo = _square_parcel_geojson(100)
        result = _mock_assessment_result()
        mock_assessment = _make_mock_assessment(assessment_id, result, parcel_geo)
        mock_db = _mock_db_returning(mock_assessment)

        resp = await get_design_constraints(assessment_id, db=mock_db)

        assert resp.assessment_id == assessment_id
        assert resp.parcel_apn == "1234-567-890"
        assert resp.envelope_geojson["type"] == "Polygon"
        assert "coordinates" in resp.envelope_geojson
        assert len(resp.per_edge_setbacks) == 4
        edge_names = {s.edge for s in resp.per_edge_setbacks}
        assert edge_names == {"front", "left_side", "right_side", "rear"}
        for s in resp.per_edge_setbacks:
            assert s.confidence == "verified"
            assert s.citation == "LAMC SS12.08"
        assert resp.height_envelope.max_height_ft == 33.0
        assert resp.height_envelope.confidence == "verified"
        assert resp.panel_fit.feasible is True
        assert resp.panel_fit.failures == []
        assert resp.material_requirements == []

    @pytest.mark.asyncio
    async def test_assessment_not_found_returns_404(self):
        from fastapi import HTTPException

        from backend.app.api.endpoints import get_design_constraints

        mock_db = _mock_db_returning(None)

        with pytest.raises(HTTPException) as exc_info:
            await get_design_constraints(uuid.uuid4(), db=mock_db)
        assert exc_info.value.status_code == 404
        assert "Assessment not found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_assessment_without_geometry_returns_404(self, assessment_id):
        from fastapi import HTTPException

        from backend.app.api.endpoints import get_design_constraints

        result = _mock_assessment_result()
        mock_assessment = _make_mock_assessment(assessment_id, result, parcel_geojson=None)
        mock_db = _mock_db_returning(mock_assessment)

        with pytest.raises(HTTPException) as exc_info:
            await get_design_constraints(assessment_id, db=mock_db)
        assert exc_info.value.status_code == 404
        assert "Assessment has no parcel geometry" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_panel_fit_infeasible(self, assessment_id):
        """Side setback of 2 ft is below the 4 ft minimum for panel delivery."""
        from backend.app.api.endpoints import get_design_constraints

        parcel_geo = _square_parcel_geojson(100)
        result = _mock_assessment_result(setback_side=2)
        mock_assessment = _make_mock_assessment(assessment_id, result, parcel_geo)
        mock_db = _mock_db_returning(mock_assessment)

        resp = await get_design_constraints(assessment_id, db=mock_db)

        assert resp.panel_fit.feasible is False
        assert len(resp.panel_fit.failures) >= 1
        assert any("Side clearance" in f for f in resp.panel_fit.failures)
        assert len(resp.panel_fit.mitigations) >= 1
