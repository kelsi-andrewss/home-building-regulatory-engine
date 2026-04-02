from __future__ import annotations

import math
import warnings

from pyproj import Transformer
from shapely.geometry import LineString, Point, mapping, shape
from shapely.geometry.polygon import Polygon
from shapely.ops import transform

# LA County uses EPSG:2229 (NAD83 California Zone 5, US feet)
_to_2229 = Transformer.from_crs("EPSG:4326", "EPSG:2229", always_xy=True).transform
_to_4326 = Transformer.from_crs("EPSG:2229", "EPSG:4326", always_xy=True).transform


def _is_wgs84(poly: Polygon) -> bool:
    """Detect WGS84 coordinates. LA County parcels have lng ~ -118, lat ~ 34.
    EPSG:2229 (feet) coordinates are in the millions for x, thousands for y.
    Test fixtures use small positive coordinates (0-150 range).
    Key signal: real WGS84 parcels in the Western hemisphere have negative x (longitude).
    """
    minx, miny, maxx, maxy = poly.bounds
    return minx < 0 and -180 <= minx and -90 <= miny <= 90


def _project_to_feet(poly: Polygon) -> Polygon:
    """Project WGS84 polygon to EPSG:2229 (feet) for LA County."""
    return transform(_to_2229, poly)


def _project_to_wgs84(poly: Polygon) -> Polygon:
    """Project EPSG:2229 polygon back to WGS84."""
    return transform(_to_4326, poly)


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
    Projects to EPSG:2229 (feet) for LA County parcels before buffering.

    Returns GeoJSON dict of the buildable envelope polygon.
    Returns empty GeoJSON polygon if setbacks consume entire parcel.
    """
    needs_proj = _is_wgs84(parcel_polygon)
    work_poly = _project_to_feet(parcel_polygon) if needs_proj else parcel_polygon

    min_setback = min(front_setback, side_setback, rear_setback)
    result = work_poly.buffer(-min_setback)

    if result.is_empty or not result.is_valid:
        return {"type": "Polygon", "coordinates": []}

    if result.geom_type == "MultiPolygon":
        result = max(result.geoms, key=lambda g: g.area)

    if needs_proj:
        result = _project_to_wgs84(result)

    return mapping(result)


def calculate_buildable_area(setback_polygon: dict) -> float:
    """Return area in square units (feet if input CRS is in feet)."""
    poly = shape(setback_polygon)
    return poly.area if poly.is_valid and not poly.is_empty else 0.0


def derive_lot_dimensions(parcel_geometry: dict) -> dict:
    """Estimate lot width and depth from minimum bounding rectangle."""
    poly = shape(parcel_geometry)
    if poly.is_empty or poly.area == 0:
        return {"width": 0.0, "depth": 0.0}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        mbr = poly.minimum_rotated_rectangle

    coords = list(mbr.exterior.coords)
    # MBR has 5 coords (closed ring), so 4 unique vertices
    edge1 = ((coords[1][0] - coords[0][0]) ** 2 + (coords[1][1] - coords[0][1]) ** 2) ** 0.5
    edge2 = ((coords[2][0] - coords[1][0]) ** 2 + (coords[2][1] - coords[1][1]) ** 2) ** 0.5

    width = min(edge1, edge2)
    depth = max(edge1, edge2)

    return {"width": width, "depth": depth}


def _edge_direction(p1: tuple, p2: tuple) -> tuple[float, float]:
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    length = math.hypot(dx, dy)
    if length == 0:
        return (0.0, 0.0)
    return (dx / length, dy / length)


def _edge_length(p1: tuple, p2: tuple) -> float:
    return math.hypot(p2[0] - p1[0], p2[1] - p1[1])


def _avg_y(p1: tuple, p2: tuple) -> float:
    return (p1[1] + p2[1]) / 2.0


def classify_parcel_edges(
    parcel_poly: Polygon,
) -> dict[str, list[LineString]]:
    """Classify parcel boundary edges as front, rear, or side using MBR frontage heuristic.

    Projects to EPSG:2229 (feet) for accurate MBR edge length comparison, then
    maps classification back to original WGS84 edges.

    MVP simplification: without street-adjacency data, assign the short MBR edge with
    the lowest y-coordinate as front (assumes south-facing parcel).

    Returns dict with keys "front", "rear", "side", each mapping to a list of LineStrings
    in the original CRS.
    """
    needs_proj = _is_wgs84(parcel_poly)
    work_poly = _project_to_feet(parcel_poly) if needs_proj else parcel_poly

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        mbr = work_poly.minimum_rotated_rectangle
    mbr_coords = list(mbr.exterior.coords)[:4]

    # Two pairs of opposite edges
    edge01 = (mbr_coords[0], mbr_coords[1])
    edge12 = (mbr_coords[1], mbr_coords[2])
    edge23 = (mbr_coords[2], mbr_coords[3])
    edge30 = (mbr_coords[3], mbr_coords[0])

    len_01 = _edge_length(*edge01)
    len_12 = _edge_length(*edge12)

    # Pair A = (edge01, edge23), Pair B = (edge12, edge30)
    if len_01 <= len_12:
        # Pair A is shorter -> front/rear; Pair B is longer -> sides
        short_pair = (edge01, edge23)
        long_pair = (edge12, edge30)
    else:
        short_pair = (edge12, edge30)
        long_pair = (edge01, edge23)

    # Front = short edge with lowest average y
    if _avg_y(*short_pair[0]) <= _avg_y(*short_pair[1]):
        front_mbr_edge, rear_mbr_edge = short_pair
    else:
        rear_mbr_edge, front_mbr_edge = short_pair

    side_mbr_edges = long_pair

    # Compute normalized directions for each MBR reference edge
    front_dir = _edge_direction(*front_mbr_edge)
    rear_dir = _edge_direction(*rear_mbr_edge)
    side_dirs = [_edge_direction(*e) for e in side_mbr_edges]

    # Classify actual parcel edges by most-parallel MBR edge
    # Work in projected coords for classification, return edges in original CRS
    result: dict[str, list[LineString]] = {"front": [], "rear": [], "side": []}
    work_coords = list(work_poly.exterior.coords)
    orig_coords = list(parcel_poly.exterior.coords)

    for i in range(len(work_coords) - 1):
        p1, p2 = work_coords[i], work_coords[i + 1]
        if _edge_length(p1, p2) < 1e-10:
            continue

        parcel_dir = _edge_direction(p1, p2)
        # Build LineString from original CRS coordinates
        ls = LineString([orig_coords[i], orig_coords[i + 1]])

        # Dot product with each MBR reference direction (absolute value for parallel check)
        dot_front = abs(parcel_dir[0] * front_dir[0] + parcel_dir[1] * front_dir[1])
        dot_rear = abs(parcel_dir[0] * rear_dir[0] + parcel_dir[1] * rear_dir[1])
        dot_side = max(
            abs(parcel_dir[0] * sd[0] + parcel_dir[1] * sd[1])
            for sd in side_dirs
        )

        best = max(dot_front, dot_rear, dot_side)
        if best == dot_side:
            result["side"].append(ls)
        elif best == dot_front:
            # Disambiguate front vs rear by proximity: use midpoint y
            edge_mid_y = _avg_y(p1, p2)
            front_mid_y = _avg_y(*front_mbr_edge)
            rear_mid_y = _avg_y(*rear_mbr_edge)
            if abs(edge_mid_y - front_mid_y) <= abs(edge_mid_y - rear_mid_y):
                result["front"].append(ls)
            else:
                result["rear"].append(ls)
        else:
            edge_mid_y = _avg_y(p1, p2)
            front_mid_y = _avg_y(*front_mbr_edge)
            rear_mid_y = _avg_y(*rear_mbr_edge)
            if abs(edge_mid_y - rear_mid_y) <= abs(edge_mid_y - front_mid_y):
                result["rear"].append(ls)
            else:
                result["front"].append(ls)

    return result


def buffer_inward_per_edge(
    parcel_poly: Polygon,
    classified_edges: dict[str, list[LineString]],
    setbacks: dict[str, float],
) -> Polygon:
    """Compute buildable envelope using per-edge setback distances.

    Projects to EPSG:2229 (feet) for LA County parcels before applying foot-based setbacks.
    Uses slab intersection: for each edge, offset inward by the setback distance,
    build a large slab polygon on the interior side, and intersect with the running result.

    Returns Shapely Polygon of buildable envelope in original CRS (empty Polygon if
    setbacks consume parcel).
    """
    needs_proj = _is_wgs84(parcel_poly)
    work_poly = _project_to_feet(parcel_poly) if needs_proj else parcel_poly

    # Project edges to same CRS as work_poly
    if needs_proj:
        work_edges: dict[str, list[LineString]] = {}
        for cls, edges in classified_edges.items():
            work_edges[cls] = [transform(_to_2229, e) for e in edges]
    else:
        work_edges = classified_edges

    result = work_poly
    margin = 10000.0

    for edge_class in ("front", "rear", "side"):
        d = setbacks.get(edge_class, 0.0)
        if d == 0:
            continue

        for edge in work_edges.get(edge_class, []):
            p1, p2 = edge.coords[0], edge.coords[1]
            dx = p2[0] - p1[0]
            dy = p2[1] - p1[1]
            length = math.hypot(dx, dy)
            if length < 1e-10:
                continue

            # Normalized edge direction
            ex, ey = dx / length, dy / length

            # Two candidate normals
            n1 = (-ey, ex)
            n2 = (ey, -ex)

            # Determine inward normal: test which normal points toward parcel interior
            mid_x = (p1[0] + p2[0]) / 2.0
            mid_y = (p1[1] + p2[1]) / 2.0
            eps = 0.1
            test1 = Point(mid_x + eps * n1[0], mid_y + eps * n1[1])
            test2 = Point(mid_x + eps * n2[0], mid_y + eps * n2[1])

            if work_poly.contains(test1):
                inward = n1
            elif work_poly.contains(test2):
                inward = n2
            else:
                # Edge might be on boundary; try larger eps
                test1 = Point(mid_x + 1.0 * n1[0], mid_y + 1.0 * n1[1])
                if work_poly.contains(test1):
                    inward = n1
                else:
                    inward = n2

            # Translate edge inward by setback distance
            offset_p1 = (p1[0] + d * inward[0], p1[1] + d * inward[1])
            offset_p2 = (p2[0] + d * inward[0], p2[1] + d * inward[1])

            # Build slab: extend setback line far along edge direction, then extend inward
            slab_coords = [
                (offset_p1[0] - margin * ex, offset_p1[1] - margin * ey),
                (offset_p2[0] + margin * ex, offset_p2[1] + margin * ey),
                (offset_p2[0] + margin * ex + margin * inward[0],
                 offset_p2[1] + margin * ey + margin * inward[1]),
                (offset_p1[0] - margin * ex + margin * inward[0],
                 offset_p1[1] - margin * ey + margin * inward[1]),
            ]
            slab = Polygon(slab_coords)

            result = result.intersection(slab)

            if result.is_empty:
                return Polygon()

    if result.is_empty or not result.is_valid:
        return Polygon()

    if result.geom_type == "MultiPolygon":
        result = max(result.geoms, key=lambda g: g.area)

    if result.geom_type != "Polygon":
        return Polygon()

    if needs_proj:
        result = _project_to_wgs84(result)

    return result
