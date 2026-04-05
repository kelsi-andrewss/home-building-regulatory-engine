"""Shared test fixtures."""

import os
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/cover_test")

import pytest
from shapely.geometry import LineString

# ---------------------------------------------------------------------------
# PDF fixture generation (session-scoped, used by test_ingestion_e2e.py)
# ---------------------------------------------------------------------------

_FIXTURES_DIR = Path(__file__).parent / "fixtures"

_HEIGHT_SETBACK_TEXT = (
    "SILVER LAKE - ECHO PARK SPECIFIC PLAN\n\n"
    "Section 7.B - Height Limit\n"
    "No building or structure shall exceed 33 feet or 2 stories in height, "
    "whichever is more restrictive. This height limit replaces the base zone "
    "height district regulations for all properties within the Specific Plan area.\n\n"
    "Section 9.A - Setbacks\n"
    "The following yard setback requirements shall apply to all new construction "
    "and additions:\n"
    "  Front yard setback: 15 feet minimum.\n"
    "  Side yard setback: 5 feet minimum for interior lots, "
    "10 feet for corner lots.\n"
    "  Rear yard setback: 15 feet.\n\n"
    "These setback requirements supplement the base zone regulations. "
    "Where the Specific Plan and base zone conflict, the more restrictive "
    "standard shall apply."
)

_DESIGN_STANDARDS_TEXT = (
    "BRENTWOOD - PACIFIC PALISADES SPECIFIC PLAN\n\n"
    "Section 12 - Design Standards\n"
    "12.A Exterior Materials\n"
    "Exterior materials shall be limited to stucco, wood siding, or stone veneer "
    "on all street-facing facades. Vinyl siding and reflective materials are "
    "prohibited.\n\n"
    "12.B Roof Standards\n"
    "Roof pitch minimum 4:12 for primary structures. Flat roofs permitted only "
    "for accessory structures under 400 square feet.\n\n"
    "12.C Building Articulation\n"
    "Building articulation required every 30 feet of continuous wall length "
    "on street-facing facades. Minimum 2-foot depth offset or projection."
)


def _make_pdf(text: str, path: Path) -> None:
    from fpdf import FPDF
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.multi_cell(0, 6, text)
    pdf.output(str(path))


@pytest.fixture(scope="session")
def height_setback_pdf() -> Path:
    path = _FIXTURES_DIR / "sample_height_setback.pdf"
    _make_pdf(_HEIGHT_SETBACK_TEXT, path)
    return path


@pytest.fixture(scope="session")
def design_standards_pdf() -> Path:
    path = _FIXTURES_DIR / "sample_design_standards.pdf"
    _make_pdf(_DESIGN_STANDARDS_TEXT, path)
    return path


@pytest.fixture(scope="session")
def malformed_pdf() -> Path:
    _FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    path = _FIXTURES_DIR / "malformed.pdf"
    path.write_bytes(b"\x00\x01\x02NOTAPDF\xff\xfe\xfd")
    return path


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
