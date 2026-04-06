"""OSM Overpass API client for fetching street centerlines near a parcel bbox."""

from __future__ import annotations

import logging

import httpx
from shapely.geometry import LineString

logger = logging.getLogger(__name__)

_OVERPASS_URL = "https://overpass-api.de/api/interpreter"

_HIGHWAY_TYPES = (
    "residential|tertiary|secondary|primary|trunk|motorway"
    "|unclassified|living_street|service"
)

# Simple dict cache keyed on rounded bbox tuple
_cache: dict[tuple, list[LineString]] = {}


def _round_bbox(bbox: tuple[float, float, float, float]) -> tuple:
    return tuple(round(v, 3) for v in bbox)


async def fetch_street_centerlines(
    bbox: tuple[float, float, float, float],
) -> list[LineString]:
    """Fetch OSM street centerlines within the given WGS84 bounding box.

    Args:
        bbox: (min_lng, min_lat, max_lng, max_lat) in WGS84 degrees.

    Returns:
        List of Shapely LineStrings in WGS84 coordinates.
        Returns empty list on any network or parse failure.
    """
    cache_key = _round_bbox(bbox)
    if cache_key in _cache:
        return _cache[cache_key]

    min_lng, min_lat, max_lng, max_lat = bbox
    # Overpass bbox format: south,west,north,east
    overpass_bbox = f"{min_lat},{min_lng},{max_lat},{max_lng}"

    query = (
        f"[out:json];"
        f'way[highway~"^({_HIGHWAY_TYPES})$"]({overpass_bbox});'
        f"(._;>;);"
        f"out body;"
    )

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(_OVERPASS_URL, data={"data": query})
        resp.raise_for_status()
        data = resp.json()

    streets = _parse_overpass_json(data)
    _cache[cache_key] = streets
    return streets


def _parse_overpass_json(data: dict) -> list[LineString]:
    """Convert Overpass JSON response into a list of LineStrings."""
    elements = data.get("elements", [])

    # Build node id -> (lng, lat) lookup
    nodes: dict[int, tuple[float, float]] = {}
    for el in elements:
        if el.get("type") == "node":
            nodes[el["id"]] = (el["lon"], el["lat"])

    streets: list[LineString] = []
    for el in elements:
        if el.get("type") != "way":
            continue
        node_ids = el.get("nodes", [])
        coords = [nodes[nid] for nid in node_ids if nid in nodes]
        if len(coords) >= 2:
            streets.append(LineString(coords))

    return streets
