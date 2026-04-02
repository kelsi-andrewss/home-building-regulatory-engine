import logging
import uuid
from datetime import UTC, datetime


def _utcnow() -> datetime:
    """Naive UTC timestamp compatible with asyncpg's 'timestamp without time zone'."""
    return datetime.now(UTC).replace(tzinfo=None)

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models import RuleFragment

logger = logging.getLogger(__name__)

# ---- Base zone rules for all 16 LA residential zones ----
# Each zone produces 7 fragments: min_lot_area, min_lot_width,
# setback_front, setback_side, setback_rear, height_max, density

_ZONE_TABLE = [
    # (zone, lamc_section, min_lot_sf, min_width_ft, front_ft, side_ft, rear_ft, height_ft, density_value, density_unit, front_value_text, rear_value_text)
    ("RE9",   "12.07.01", 9000,  65,  25,  10,  25, 33, 1,    "unit/lot", "20% depth, max 25'", "25% depth, max 25'"),
    ("RE11",  "12.07.01", 11000, 70,  25,  10,  25, 33, 1,    "unit/lot", "20% depth, max 25'", "25% depth, max 25'"),
    ("RE15",  "12.07.01", 15000, 80,  25,  10,  25, 33, 1,    "unit/lot", "20% depth, max 25'", "25% depth, max 25'"),
    ("RE20",  "12.07.01", 20000, 100, 25,  10,  25, 33, 1,    "unit/lot", "20% depth, max 25'", "25% depth, max 25'"),
    ("RE40",  "12.07.01", 40000, 150, 25,  10,  25, 33, 1,    "unit/lot", "20% depth, max 25'", "25% depth, max 25'"),
    ("RS",    "12.07.1",  7500,  60,  25,  5,   20, 33, 1,    "unit/lot", "20% depth, max 25'", None),
    ("R1",    "12.08",    5000,  50,  20,  5,   15, 33, 1,    "unit/lot", "20% depth, max 20'", None),
    ("R2",    "12.09",    5000,  50,  20,  5,   15, 33, 2500, "sf",       "20% depth, max 20'", None),
    ("RD6",   "12.09.1",  6000,  50,  20,  5,   15, 45, 6000, "sf",       None, None),
    ("RD5",   "12.09.1",  5000,  50,  20,  5,   15, 45, 5000, "sf",       None, None),
    ("RD4",   "12.09.1",  5000,  50,  20,  7.5, 15, 45, 4000, "sf",       None, None),
    ("RD3",   "12.09.1",  5000,  50,  20,  7.5, 15, 45, 3000, "sf",       None, None),
    ("RD2",   "12.09.1",  5000,  50,  20,  5,   15, 45, 2000, "sf",       None, None),
    ("RD1.5", "12.09.1",  5000,  50,  20,  5,   15, 45, 1500, "sf",       None, None),
    ("R3",    "12.10",    5000,  50,  15,  5,   15, 45, 800,  "sf",       None, None),
    ("R4",    "12.11",    5000,  50,  15,  5,   15, 45, 400,  "sf",       None, None),
]


def _build_base_zone_fragments() -> list[dict]:
    fragments = []
    now = _utcnow()

    for (zone, section, min_lot, min_width, front, side, rear,
         height, density_val, density_unit, front_text, rear_text) in _ZONE_TABLE:

        source_doc = f"LAMC \u00a7{section}"
        base = {
            "source_document": source_doc,
            "source_section": f"\u00a7{section}",
            "zone_applicability": [zone],
            "confidence": "verified",
            "overrides_base_zone": False,
            "extracted_at": now,
        }

        fragments.append({
            **base,
            "constraint_type": "min_lot_area",
            "value": float(min_lot),
            "unit": "sf",
        })
        fragments.append({
            **base,
            "constraint_type": "min_lot_width",
            "value": float(min_width),
            "unit": "ft",
        })
        fragments.append({
            **base,
            "constraint_type": "setback_front",
            "value": float(front),
            "value_text": front_text,
            "unit": "ft",
        })
        fragments.append({
            **base,
            "constraint_type": "setback_side",
            "value": float(side),
            "unit": "ft",
        })
        fragments.append({
            **base,
            "constraint_type": "setback_rear",
            "value": float(rear),
            "value_text": rear_text,
            "unit": "ft",
        })
        fragments.append({
            **base,
            "constraint_type": "height_max",
            "value": float(height),
            "unit": "ft",
        })

        if density_unit == "unit/lot":
            fragments.append({
                **base,
                "constraint_type": "density",
                "value": float(density_val),
                "value_text": "1 unit per lot",
                "unit": "unit/lot",
            })
        else:
            fragments.append({
                **base,
                "constraint_type": "density",
                "value": float(density_val),
                "value_text": f"1 unit per {density_val} sf of lot area",
                "unit": "sf",
            })

    return fragments


# ---- Height district modifiers ----
# HD modifiers apply to zone categories, not individual zones.

_HEIGHT_DISTRICTS = [
    # (hd, sf_height, mf_height, mf_far)
    ("1",   33, 45, 3.0),
    ("1L",  33, 35, 3.0),
    ("1VL", 33, 33, 3.0),
    ("1XL", 33, 30, 3.0),
    ("1SS", 33, 30, 3.0),
]


def _build_height_district_fragments() -> list[dict]:
    fragments = []
    now = _utcnow()

    for hd, sf_height, mf_height, mf_far in _HEIGHT_DISTRICTS:
        base = {
            "source_document": f"LAMC Height District {hd}",
            "source_section": "\u00a712.21.1",
            "confidence": "verified",
            "overrides_base_zone": False,
            "extracted_at": now,
        }

        # Single-family zones
        sf_zones = ["RE9", "RE11", "RE15", "RE20", "RE40", "RS", "R1"]
        fragments.append({
            **base,
            "zone_applicability": sf_zones,
            "constraint_type": "height_max",
            "value": float(sf_height),
            "value_text": f"Height District {hd} single-family max",
            "unit": "ft",
            "condition": f"height_district={hd}",
        })

        # Multi-family zones
        mf_zones = ["R2", "RD1.5", "RD2", "RD3", "RD4", "RD5", "RD6", "R3", "R4"]
        fragments.append({
            **base,
            "zone_applicability": mf_zones,
            "constraint_type": "height_max",
            "value": float(mf_height),
            "value_text": f"Height District {hd} multi-family max",
            "unit": "ft",
            "condition": f"height_district={hd}",
        })

        # FAR for multi-family
        fragments.append({
            **base,
            "zone_applicability": mf_zones,
            "constraint_type": "far_max",
            "value": mf_far,
            "value_text": f"Height District {hd} FAR",
            "unit": "ratio",
            "condition": f"height_district={hd}",
        })

    return fragments


# ---- ADU state law rules ----

def _build_adu_fragments() -> list[dict]:
    now = _utcnow()
    source = "CA Gov. Code \u00a765852.2"
    base = {
        "source_document": source,
        "source_section": "\u00a765852.2",
        "zone_applicability": ["all"],
        "confidence": "verified",
        "overrides_base_zone": True,
        "extracted_at": now,
        "condition": "ADU",
    }

    return [
        {
            **base,
            "constraint_type": "setback_side",
            "value": 4.0,
            "unit": "ft",
            "value_text": "4 ft max side setback for ADU",
        },
        {
            **base,
            "constraint_type": "setback_rear",
            "value": 4.0,
            "unit": "ft",
            "value_text": "4 ft max rear setback for ADU",
        },
        {
            **base,
            "constraint_type": "height_max",
            "value": 16.0,
            "unit": "ft",
            "value_text": "16 ft guaranteed; 18 ft near transit; 25 ft if attached",
        },
        {
            **base,
            "constraint_type": "size_floor",
            "value": 800.0,
            "unit": "sf",
            "value_text": "800 sf guaranteed minimum",
        },
        {
            **base,
            "constraint_type": "size_max_detached",
            "value": 1200.0,
            "unit": "sf",
            "value_text": "1,200 sf max detached ADU",
        },
        {
            **base,
            "constraint_type": "size_max_attached",
            "value": 1200.0,
            "unit": "sf",
            "value_text": "lesser of 1,200 sf or 50% of primary dwelling",
        },
        {
            **base,
            "constraint_type": "size_max_jadu",
            "value": 500.0,
            "unit": "sf",
            "value_text": "500 sf max JADU",
        },
    ]


async def seed_base_zones(session: AsyncSession) -> int:
    existing = await session.execute(
        select(RuleFragment.id).where(
            RuleFragment.confidence == "verified",
            RuleFragment.source_document.like("LAMC%"),
        )
    )
    if existing.scalars().first() is not None:
        logger.info("Base zone fragments already exist, skipping")
        return 0

    fragments = _build_base_zone_fragments()
    count = 0
    for frag_data in fragments:
        frag = RuleFragment(id=uuid.uuid4(), **frag_data)
        session.add(frag)
        count += 1

    await session.flush()
    logger.info("Inserted %d base zone fragments", count)
    return count


async def seed_height_districts(session: AsyncSession) -> int:
    existing = await session.execute(
        select(RuleFragment.id).where(
            RuleFragment.source_document.like("LAMC Height District%"),
        )
    )
    if existing.scalars().first() is not None:
        logger.info("Height district fragments already exist, skipping")
        return 0

    fragments = _build_height_district_fragments()
    count = 0
    for frag_data in fragments:
        frag = RuleFragment(id=uuid.uuid4(), **frag_data)
        session.add(frag)
        count += 1

    await session.flush()
    logger.info("Inserted %d height district fragments", count)
    return count


async def seed_adu_rules(session: AsyncSession) -> int:
    existing = await session.execute(
        select(RuleFragment.id).where(
            RuleFragment.source_document.like("%Gov. Code%"),
        )
    )
    if existing.scalars().first() is not None:
        logger.info("ADU fragments already exist, skipping")
        return 0

    fragments = _build_adu_fragments()
    count = 0
    for frag_data in fragments:
        frag = RuleFragment(id=uuid.uuid4(), **frag_data)
        session.add(frag)
        count += 1

    await session.flush()
    logger.info("Inserted %d ADU fragments", count)
    return count


async def seed_all(session: AsyncSession) -> int:
    total = 0
    total += await seed_base_zones(session)
    total += await seed_height_districts(session)
    total += await seed_adu_rules(session)
    logger.info("Seed complete: %d total fragments inserted", total)
    return total
