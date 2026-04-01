from __future__ import annotations

from shapely.geometry import mapping, shape
from shapely.geometry.polygon import Polygon


def parcel_polygon_from_geojson(geojson: dict) -> Polygon:
    """Convert GeoJSON polygon dict to Shapely Polygon."""
    return shape(geojson)


def buffer_inward(
    parcel_polygon: Polygon,
    front_setback: float,
    side_setback: float,
    rear_setback: float,
) -> dict:
    """Compute buildable envelope by buffering inward from parcel edges.

    MVP simplification: use min(front, side, rear) as uniform negative buffer.
    This is conservative (underestimates buildable area) but geometrically correct.

    Returns GeoJSON dict of the buildable envelope polygon.
    Returns empty GeoJSON polygon if setbacks consume entire parcel.
    """
    min_setback = min(front_setback, side_setback, rear_setback)

    result = parcel_polygon.buffer(-min_setback)

    if result.is_empty or not result.is_valid:
        return {"type": "Polygon", "coordinates": []}

    # buffer can return MultiPolygon in edge cases; take largest
    if result.geom_type == "MultiPolygon":
        result = max(result.geoms, key=lambda g: g.area)

    return mapping(result)


def calculate_buildable_area(setback_polygon: dict) -> float:
    """Return area in square units (feet if input CRS is in feet)."""
    poly = shape(setback_polygon)
    return poly.area if poly.is_valid and not poly.is_empty else 0.0


def derive_lot_dimensions(parcel_geometry: dict) -> dict:
    """Estimate lot width and depth from minimum bounding rectangle."""
    poly = shape(parcel_geometry)
    mbr = poly.minimum_rotated_rectangle

    coords = list(mbr.exterior.coords)
    # MBR has 5 coords (closed ring), so 4 unique vertices
    edge1 = ((coords[1][0] - coords[0][0]) ** 2 + (coords[1][1] - coords[0][1]) ** 2) ** 0.5
    edge2 = ((coords[2][0] - coords[1][0]) ** 2 + (coords[2][1] - coords[1][1]) ** 2) ** 0.5

    width = min(edge1, edge2)
    depth = max(edge1, edge2)

    return {"width": width, "depth": depth}
