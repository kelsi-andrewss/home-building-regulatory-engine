import re
from dataclasses import dataclass

KNOWN_HEIGHT_DISTRICTS = ("1SS", "1XL", "1VL", "1L", "1")


@dataclass
class ParsedZone:
    zone_class: str
    height_district: str
    raw: str


def parse_zone(zone_cmplt: str) -> ParsedZone:
    """Split ZONE_CMPLT (e.g. 'R1-1', 'RD1.5-1VL', 'RE40-1L') into class and height district.

    Handles prefixes like [Q] and suffixes like -CPIO by stripping them first.
    Raises ValueError for unparseable input.
    """
    if not zone_cmplt or not zone_cmplt.strip():
        raise ValueError(f"Empty zone string: {zone_cmplt!r}")

    raw = zone_cmplt.strip()
    working = raw

    # Strip Q-condition prefix: [Q]R1-1 -> R1-1
    working = re.sub(r"^\[Q\]", "", working)

    # Strip known suffix overlays: R1-1-CPIO -> R1-1
    working = re.sub(r"-(?:CPIO|CUGU|CDO|HPOZ|RFA|NSO)$", "", working)

    # Find all dash positions
    dash_positions = [i for i, c in enumerate(working) if c == "-"]

    if not dash_positions:
        raise ValueError(f"No height district separator found in: {raw!r}")

    # Try each dash from right to left: the suffix after the dash must be
    # a known height district.
    for pos in reversed(dash_positions):
        suffix = working[pos + 1:]
        if suffix in KNOWN_HEIGHT_DISTRICTS:
            zone_class = working[:pos]
            if not zone_class:
                raise ValueError(f"Empty zone class in: {raw!r}")
            return ParsedZone(zone_class=zone_class, height_district=suffix, raw=raw)

    raise ValueError(f"No known height district found in: {raw!r}")
