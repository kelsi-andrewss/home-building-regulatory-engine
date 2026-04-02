import pytest

from shapely.geometry.polygon import Polygon

from backend.app.engine.geometry_utils import (
    buffer_inward,
    buffer_inward_per_edge,
    calculate_buildable_area,
    classify_parcel_edges,
    derive_lot_dimensions,
    parcel_polygon_from_geojson,
)
from backend.tests.conftest import make_la_parcel_geojson as _la_parcel
from backend.tests.conftest import make_rect_parcel as _rect_parcel
from backend.tests.conftest import make_square_parcel as _square_parcel


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


class TestClassifyParcelEdges:
    def test_rectangular_parcel_classification(self):
        """50x120 rect parcel: short edges (50') = front/rear, long edges (120') = side."""
        poly = parcel_polygon_from_geojson(_rect_parcel(50, 120))
        edges = classify_parcel_edges(poly)

        assert "front" in edges
        assert "rear" in edges
        assert "side" in edges
        assert len(edges["front"]) > 0
        assert len(edges["rear"]) > 0
        assert len(edges["side"]) > 0

        # Total classified edges should equal number of boundary segments
        total = len(edges["front"]) + len(edges["rear"]) + len(edges["side"])
        n_boundary_segments = len(list(poly.exterior.coords)) - 1
        assert total == n_boundary_segments

    def test_square_parcel_classification(self):
        """100x100 square: ambiguous but should still produce valid output with all keys."""
        poly = parcel_polygon_from_geojson(_square_parcel(100))
        edges = classify_parcel_edges(poly)

        assert "front" in edges
        assert "rear" in edges
        assert "side" in edges
        # All edges should be accounted for
        total = len(edges["front"]) + len(edges["rear"]) + len(edges["side"])
        n_boundary_segments = len(list(poly.exterior.coords)) - 1
        assert total == n_boundary_segments

    def test_all_edges_accounted_for(self):
        """Every boundary segment of the parcel should appear in exactly one class."""
        for geojson_fn in [lambda: _square_parcel(80), lambda: _rect_parcel(60, 150)]:
            geojson = geojson_fn()
            poly = parcel_polygon_from_geojson(geojson)
            edges = classify_parcel_edges(poly)

            total = len(edges["front"]) + len(edges["rear"]) + len(edges["side"])
            n_boundary_segments = len(list(poly.exterior.coords)) - 1
            assert total == n_boundary_segments


class TestBufferInwardPerEdge:
    def test_nonuniform_setbacks_rectangular(self):
        """50x120 rect with front=20, side=5, rear=15. Expected ~40*85 = 3400 sf."""
        poly = parcel_polygon_from_geojson(_rect_parcel(50, 120))
        edges = classify_parcel_edges(poly)
        result = buffer_inward_per_edge(poly, edges, {"front": 20, "side": 5, "rear": 15})

        assert not result.is_empty
        area = result.area
        assert 3300 < area < 3500, f"Expected ~3400 sf, got {area}"

    def test_uniform_setbacks_matches_buffer_inward(self):
        """100x100 square with 10/10/10: per-edge result should be close to uniform buffer."""
        poly = parcel_polygon_from_geojson(_square_parcel(100))
        edges = classify_parcel_edges(poly)
        per_edge_result = buffer_inward_per_edge(poly, edges, {"front": 10, "side": 10, "rear": 10})

        uniform_result = buffer_inward(poly, front_setback=10, side_setback=10, rear_setback=10)
        uniform_area = calculate_buildable_area(uniform_result)

        per_edge_area = per_edge_result.area
        # Both should be close to 6400 sf; allow 5% tolerance
        assert abs(per_edge_area - uniform_area) / uniform_area < 0.05, (
            f"Per-edge area {per_edge_area} vs uniform area {uniform_area}"
        )

    def test_setbacks_consume_parcel(self):
        """40x40 parcel with 25' setbacks on all sides -> empty polygon."""
        poly = parcel_polygon_from_geojson(_square_parcel(40))
        edges = classify_parcel_edges(poly)
        result = buffer_inward_per_edge(poly, edges, {"front": 25, "side": 25, "rear": 25})

        assert result.is_empty

    def test_returns_polygon_type(self):
        """Result should be a Shapely Polygon, not a GeoJSON dict."""
        poly = parcel_polygon_from_geojson(_rect_parcel(50, 120))
        edges = classify_parcel_edges(poly)
        result = buffer_inward_per_edge(poly, edges, {"front": 20, "side": 5, "rear": 15})

        assert isinstance(result, Polygon)


class TestWGS84Projection:
    """Tests using real WGS84 coordinates to verify CRS projection works."""

    def test_buffer_inward_wgs84_produces_nonempty(self):
        """A ~50x120ft LA parcel with 5ft setbacks should produce a non-empty envelope."""
        poly = parcel_polygon_from_geojson(_la_parcel())
        result = buffer_inward(poly, front_setback=5, side_setback=5, rear_setback=5)

        assert result["type"] == "Polygon"
        assert len(result["coordinates"]) > 0
        assert len(result["coordinates"][0]) > 0

    def test_buffer_inward_wgs84_result_is_wgs84(self):
        """Buffered result should be back in WGS84 (lng ~ -118, lat ~ 34)."""
        poly = parcel_polygon_from_geojson(_la_parcel())
        result = buffer_inward(poly, front_setback=5, side_setback=5, rear_setback=5)

        coords = result["coordinates"][0]
        for lng, lat in coords:
            assert -119 < lng < -117, f"lng {lng} not in LA range"
            assert 33 < lat < 35, f"lat {lat} not in LA range"

    def test_classify_edges_wgs84(self):
        """Edge classification works on WGS84 parcels, returns WGS84 LineStrings."""
        poly = parcel_polygon_from_geojson(_la_parcel())
        edges = classify_parcel_edges(poly)

        assert len(edges["front"]) > 0
        assert len(edges["side"]) > 0
        total = len(edges["front"]) + len(edges["rear"]) + len(edges["side"])
        assert total == len(list(poly.exterior.coords)) - 1

        # Edges should be in WGS84
        for cls_edges in edges.values():
            for edge in cls_edges:
                for coord in edge.coords:
                    assert -119 < coord[0] < -117

    def test_per_edge_buffer_wgs84_nonempty(self):
        """Per-edge buffering with R1 setbacks on a WGS84 parcel produces non-empty result."""
        poly = parcel_polygon_from_geojson(_la_parcel())
        edges = classify_parcel_edges(poly)
        result = buffer_inward_per_edge(poly, edges, {"front": 20, "side": 5, "rear": 15})

        assert isinstance(result, Polygon)
        assert not result.is_empty
        # Result should be in WGS84
        minx, miny, maxx, maxy = result.bounds
        assert -119 < minx < -117
        assert 33 < miny < 35

    def test_per_edge_buffer_wgs84_smaller_than_parcel(self):
        """Buffered envelope should be strictly smaller than the original parcel."""
        poly = parcel_polygon_from_geojson(_la_parcel())
        edges = classify_parcel_edges(poly)
        result = buffer_inward_per_edge(poly, edges, {"front": 5, "side": 5, "rear": 5})

        assert result.area < poly.area
