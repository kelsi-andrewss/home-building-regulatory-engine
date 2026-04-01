import pytest

from backend.app.engine.geometry_utils import (
    buffer_inward,
    calculate_buildable_area,
    derive_lot_dimensions,
    parcel_polygon_from_geojson,
)


def _square_parcel(size: float = 100) -> dict:
    """Return a GeoJSON polygon for a size x size square parcel."""
    return {
        "type": "Polygon",
        "coordinates": [
            [[0, 0], [size, 0], [size, size], [0, size], [0, 0]]
        ],
    }


def _rect_parcel(width: float = 50, depth: float = 120) -> dict:
    return {
        "type": "Polygon",
        "coordinates": [
            [[0, 0], [width, 0], [width, depth], [0, depth], [0, 0]]
        ],
    }


class TestBufferInward:
    def test_square_uniform_setbacks(self):
        """100x100 parcel with 10' uniform setbacks -> buildable area ~ 6400 sf."""
        parcel = parcel_polygon_from_geojson(_square_parcel(100))
        result = buffer_inward(parcel, front_setback=10, side_setback=10, rear_setback=10)

        assert result["type"] == "Polygon"
        assert len(result["coordinates"]) > 0
        area = calculate_buildable_area(result)
        # Shapely buffer rounds corners, so area will be slightly less than 6400
        assert 6300 < area <= 6400

    def test_setbacks_consume_parcel(self):
        """50' setbacks on a 40' wide parcel -> empty polygon."""
        parcel = parcel_polygon_from_geojson(_square_parcel(40))
        result = buffer_inward(parcel, front_setback=50, side_setback=50, rear_setback=50)

        assert result["type"] == "Polygon"
        assert result["coordinates"] == []

    def test_rectangular_parcel(self):
        """50x120 parcel with 5' uniform setbacks -> ~ 40*110 = 4400 sf."""
        parcel = parcel_polygon_from_geojson(_rect_parcel(50, 120))
        result = buffer_inward(parcel, front_setback=5, side_setback=5, rear_setback=5)

        area = calculate_buildable_area(result)
        assert 4350 < area <= 4400

    def test_uses_min_setback(self):
        """When setbacks differ, MVP uses min. 100x100 parcel with 5/10/15 -> buffer by 5."""
        parcel = parcel_polygon_from_geojson(_square_parcel(100))
        result = buffer_inward(parcel, front_setback=15, side_setback=5, rear_setback=10)

        area = calculate_buildable_area(result)
        # Buffered by 5 on each side: 90x90 = 8100
        assert 8000 < area <= 8100


class TestGeoJSONRoundTrip:
    def test_geojson_to_polygon_and_back(self):
        geojson = _square_parcel(100)
        poly = parcel_polygon_from_geojson(geojson)
        assert poly.area == 10000

        result = buffer_inward(poly, 10, 10, 10)
        assert result["type"] == "Polygon"
        assert len(result["coordinates"]) > 0


class TestDeriveLotDimensions:
    def test_rectangular_lot(self):
        geojson = _rect_parcel(50, 120)
        dims = derive_lot_dimensions(geojson)
        assert abs(dims["width"] - 50) < 0.1
        assert abs(dims["depth"] - 120) < 0.1

    def test_square_lot(self):
        geojson = _square_parcel(100)
        dims = derive_lot_dimensions(geojson)
        assert abs(dims["width"] - 100) < 0.1
        assert abs(dims["depth"] - 100) < 0.1
