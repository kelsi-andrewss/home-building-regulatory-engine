import pytest

from backend.app.engine.zone_parser import ParsedZone, parse_zone


class TestParseZone:
    def test_r1_1(self):
        result = parse_zone("R1-1")
        assert result == ParsedZone(zone_class="R1", height_district="1", raw="R1-1")

    def test_rd1_5_1vl(self):
        result = parse_zone("RD1.5-1VL")
        assert result == ParsedZone(zone_class="RD1.5", height_district="1VL", raw="RD1.5-1VL")

    def test_re40_1l(self):
        result = parse_zone("RE40-1L")
        assert result == ParsedZone(zone_class="RE40", height_district="1L", raw="RE40-1L")

    def test_r1_1xl(self):
        result = parse_zone("R1-1XL")
        assert result == ParsedZone(zone_class="R1", height_district="1XL", raw="R1-1XL")

    def test_rs_1(self):
        result = parse_zone("RS-1")
        assert result == ParsedZone(zone_class="RS", height_district="1", raw="RS-1")

    def test_r2_1ss(self):
        result = parse_zone("R2-1SS")
        assert result == ParsedZone(zone_class="R2", height_district="1SS", raw="R2-1SS")

    def test_r3_1(self):
        result = parse_zone("R3-1")
        assert result == ParsedZone(zone_class="R3", height_district="1", raw="R3-1")

    def test_r4_1(self):
        result = parse_zone("R4-1")
        assert result == ParsedZone(zone_class="R4", height_district="1", raw="R4-1")

    def test_rd6_1(self):
        result = parse_zone("RD6-1")
        assert result == ParsedZone(zone_class="RD6", height_district="1", raw="RD6-1")

    def test_q_prefix_stripped(self):
        result = parse_zone("[Q]R1-1")
        assert result.zone_class == "R1"
        assert result.height_district == "1"

    def test_cpio_suffix_stripped(self):
        result = parse_zone("R1-1-CPIO")
        assert result.zone_class == "R1"
        assert result.height_district == "1"

    def test_garbage_raises(self):
        with pytest.raises(ValueError):
            parse_zone("GARBAGE")

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            parse_zone("")

    def test_whitespace_stripped(self):
        result = parse_zone("  R1-1  ")
        assert result.zone_class == "R1"
        assert result.height_district == "1"
