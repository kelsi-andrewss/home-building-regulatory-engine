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


def make_la_parcel_geojson() -> dict:
    """A realistic ~50x120ft residential parcel in LA (WGS84 coordinates).

    Located near Vermont Ave, Los Angeles. Approximate rectangle.
    At LA latitude, 1 degree lng ~ 288,200 ft, 1 degree lat ~ 364,000 ft.
    50ft wide ~ 0.000173 deg lng, 120ft deep ~ 0.000330 deg lat.
    """
    lng, lat = -118.2920, 34.0760
    w = 0.000173  # ~50ft in lng degrees
    h = 0.000330  # ~120ft in lat degrees
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [lng, lat],
                [lng + w, lat],
                [lng + w, lat + h],
                [lng, lat + h],
                [lng, lat],
            ]
        ],
    }
