"""Tests for street-proximity-based parcel edge classification and overpass client parsing."""

from __future__ import annotations

import pytest
from shapely.geometry import LineString
from shapely.geometry.polygon import Polygon

from backend.app.engine.geometry_utils import classify_parcel_edges
from backend.app.clients.overpass_client import _parse_overpass_json


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rect_poly(width: float, depth: float) -> Polygon:
    """Axis-aligned rectangle in local (non-WGS84) coordinates."""
    return Polygon([(0, 0), (width, 0), (width, depth), (0, depth)])


# ---------------------------------------------------------------------------
# classify_parcel_edges with street_geometries
# ---------------------------------------------------------------------------

class TestStreetProximityClassification:
    def test_south_edge_near_street_is_front(self):
        """Street running along the south edge (y ~ -5) → south edge classified as front."""
        poly = _rect_poly(50, 120)
        # Street runs just below the south edge of the parcel
        street = LineString([(-10, -5), (60, -5)])
        edges = classify_parcel_edges(poly, street_geometries=[street])

        assert len(edges["front"]) > 0
        # The front edge(s) should be the south edge (y ~ 0)
        for edge in edges["front"]:
            ys = [c[1] for c in edge.coords]
            assert all(abs(y) < 1.0 for y in ys), f"Expected south edge near y=0, got {ys}"

    def test_corner_lot_two_streets_both_front(self):
        """Streets along north and east edges → both edges classified as front."""
        poly = _rect_poly(50, 120)
        # Streets run along the north (y~125) and east (x~55) edges of the parcel.
        # Both are within 10 units — well under the 50ft threshold.
        # All-positive coords avoids false WGS84 detection in _is_wgs84_linestring.
        street_north = LineString([(10, 125), (60, 125)])
        street_east = LineString([(55, 10), (55, 130)])
        edges = classify_parcel_edges(poly, street_geometries=[street_north, street_east])

        assert len(edges["front"]) >= 2

    def test_no_streets_falls_back_to_mbr(self):
        """Passing no streets produces same result as calling without the parameter."""
        poly = _rect_poly(50, 120)
        edges_no_arg = classify_parcel_edges(poly)
        edges_empty = classify_parcel_edges(poly, street_geometries=[])
        edges_none = classify_parcel_edges(poly, street_geometries=None)

        assert len(edges_no_arg["front"]) == len(edges_empty["front"])
        assert len(edges_no_arg["front"]) == len(edges_none["front"])
        assert len(edges_no_arg["side"]) == len(edges_empty["side"])
        assert len(edges_no_arg["rear"]) == len(edges_none["rear"])

    def test_all_edges_accounted_for_with_streets(self):
        """With street geometries, every boundary segment still lands in exactly one class."""
        poly = _rect_poly(50, 120)
        street = LineString([(-10, -5), (60, -5)])
        edges = classify_parcel_edges(poly, street_geometries=[street])

        total = len(edges["front"]) + len(edges["rear"]) + len(edges["side"])
        n_boundary = len(list(poly.exterior.coords)) - 1
        assert total == n_boundary

    def test_distant_street_does_not_affect_classification(self):
        """A street >50ft away should not override MBR classification."""
        poly = _rect_poly(50, 120)
        # Street is 200ft to the north — well outside the 50ft threshold
        street = LineString([(-10, 320), (60, 320)])
        edges_with_distant = classify_parcel_edges(poly, street_geometries=[street])
        edges_mbr = classify_parcel_edges(poly)

        assert len(edges_with_distant["front"]) == len(edges_mbr["front"])
        assert len(edges_with_distant["side"]) == len(edges_mbr["side"])
        assert len(edges_with_distant["rear"]) == len(edges_mbr["rear"])


# ---------------------------------------------------------------------------
# Overpass client response parsing
# ---------------------------------------------------------------------------

class TestOverpassClientParsing:
    def _make_response(self) -> dict:
        return {
            "elements": [
                {"type": "node", "id": 1, "lon": -118.292, "lat": 34.076},
                {"type": "node", "id": 2, "lon": -118.291, "lat": 34.076},
                {"type": "node", "id": 3, "lon": -118.290, "lat": 34.076},
                {
                    "type": "way",
                    "id": 100,
                    "nodes": [1, 2, 3],
                    "tags": {"highway": "residential"},
                },
            ]
        }

    def test_parses_way_into_linestring(self):
        data = self._make_response()
        streets = _parse_overpass_json(data)
        assert len(streets) == 1
        assert isinstance(streets[0], LineString)
        assert len(list(streets[0].coords)) == 3

    def test_coords_are_lon_lat(self):
        data = self._make_response()
        streets = _parse_overpass_json(data)
        coords = list(streets[0].coords)
        # Longitude should be negative (LA), latitude positive
        for lon, lat in coords:
            assert lon < 0
            assert lat > 0

    def test_empty_elements_returns_empty_list(self):
        streets = _parse_overpass_json({"elements": []})
        assert streets == []

    def test_way_with_missing_nodes_skipped(self):
        """A way referencing unknown node ids produces no street."""
        data = {
            "elements": [
                {"type": "way", "id": 200, "nodes": [999, 1000], "tags": {"highway": "residential"}},
            ]
        }
        streets = _parse_overpass_json(data)
        assert streets == []

    def test_way_with_single_node_skipped(self):
        """A way with only one resolved node cannot form a LineString and is skipped."""
        data = {
            "elements": [
                {"type": "node", "id": 1, "lon": -118.292, "lat": 34.076},
                {"type": "way", "id": 300, "nodes": [1], "tags": {"highway": "residential"}},
            ]
        }
        streets = _parse_overpass_json(data)
        assert streets == []

    def test_multiple_ways_parsed(self):
        data = {
            "elements": [
                {"type": "node", "id": 1, "lon": -118.292, "lat": 34.076},
                {"type": "node", "id": 2, "lon": -118.291, "lat": 34.076},
                {"type": "node", "id": 3, "lon": -118.292, "lat": 34.077},
                {"type": "node", "id": 4, "lon": -118.291, "lat": 34.077},
                {"type": "way", "id": 101, "nodes": [1, 2], "tags": {"highway": "tertiary"}},
                {"type": "way", "id": 102, "nodes": [3, 4], "tags": {"highway": "secondary"}},
            ]
        }
        streets = _parse_overpass_json(data)
        assert len(streets) == 2
