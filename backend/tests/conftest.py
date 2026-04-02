"""Shared test fixtures for geometry-based tests."""

from shapely.geometry import LineString


def make_square_parcel(size: float = 100) -> dict:
    """Return a GeoJSON polygon for a size x size square parcel."""
    return {
        "type": "Polygon",
        "coordinates": [
            [[0, 0], [size, 0], [size, size], [0, size], [0, 0]]
        ],
    }


def make_rect_parcel(width: float = 50, depth: float = 120) -> dict:
    """Return a GeoJSON polygon for a width x depth rectangle."""
    return {
        "type": "Polygon",
        "coordinates": [
            [[0, 0], [width, 0], [width, depth], [0, depth], [0, 0]]
        ],
    }


def make_empty_geojson() -> dict:
    return {"type": "Polygon", "coordinates": []}


def make_dummy_classified_edges() -> dict[str, list[LineString]]:
    """Dummy classified edges matching classify_parcel_edges return type."""
    return {"front": [], "rear": [], "side": []}
