import pytest

from backend.app.engine.panel_fit import (
    MIN_ENVELOPE_WIDTH_FT,
    MIN_SIDE_CLEARANCE_FT,
    PanelFitResult,
    check_panel_fit,
)
from backend.tests.conftest import (
    make_dummy_classified_edges,
    make_empty_geojson as _empty_envelope,
    make_rect_parcel as _rect_envelope,
)

_DUMMY_EDGES = make_dummy_classified_edges()


class TestPanelFitSuccess:
    """Both checks pass -- panels fit normally."""

    def test_wide_lot_ample_clearance(self):
        result = check_panel_fit(
            buildable_envelope=_rect_envelope(50, 120),
            classified_edges=_DUMMY_EDGES,
            side_setbacks=5.0,
        )
        assert result.feasible is True
        assert result.failures == []
        assert result.mitigations == []
        assert result.min_side_clearance == 5.0
        assert abs(result.min_envelope_width - 50.0) < 0.1

    def test_exact_thresholds_pass(self):
        """Exactly 4.0 clearance and exactly 8.0 width should pass."""
        result = check_panel_fit(
            buildable_envelope=_rect_envelope(8.0, 20.0),
            classified_edges=_DUMMY_EDGES,
            side_setbacks=4.0,
        )
        assert result.feasible is True
        assert result.failures == []
        assert result.min_side_clearance == 4.0
        assert abs(result.min_envelope_width - 8.0) < 0.1


class TestSideClearanceFailure:
    """Side clearance below 4' triggers crane mitigation."""

    def test_narrow_clearance(self):
        result = check_panel_fit(
            buildable_envelope=_rect_envelope(50, 120),
            classified_edges=_DUMMY_EDGES,
            side_setbacks=3.0,
        )
        assert result.feasible is False
        assert len(result.failures) == 1
        assert "Side clearance" in result.failures[0]
        assert len(result.mitigations) == 1
        assert "Crane" in result.mitigations[0]

    def test_zero_clearance(self):
        result = check_panel_fit(
            buildable_envelope=_rect_envelope(50, 120),
            classified_edges=_DUMMY_EDGES,
            side_setbacks=0.0,
        )
        assert result.feasible is False
        assert result.min_side_clearance == 0.0
        assert any("Crane" in m for m in result.mitigations)

    def test_just_below_threshold(self):
        result = check_panel_fit(
            buildable_envelope=_rect_envelope(50, 120),
            classified_edges=_DUMMY_EDGES,
            side_setbacks=3.99,
        )
        assert result.feasible is False
        assert len(result.failures) == 1


class TestEnvelopeWidthFailure:
    """Envelope width below 8' triggers custom-panel mitigation."""

    def test_narrow_envelope(self):
        result = check_panel_fit(
            buildable_envelope=_rect_envelope(6.0, 40.0),
            classified_edges=_DUMMY_EDGES,
            side_setbacks=5.0,
        )
        assert result.feasible is False
        assert len(result.failures) == 1
        assert "Envelope width" in result.failures[0]
        assert len(result.mitigations) == 1
        assert "Custom" in result.mitigations[0]

    def test_empty_envelope(self):
        result = check_panel_fit(
            buildable_envelope=_empty_envelope(),
            classified_edges=_DUMMY_EDGES,
            side_setbacks=5.0,
        )
        assert result.feasible is False
        assert result.min_envelope_width == 0.0
        assert any("Custom" in m for m in result.mitigations)

    def test_just_below_width_threshold(self):
        result = check_panel_fit(
            buildable_envelope=_rect_envelope(7.99, 40.0),
            classified_edges=_DUMMY_EDGES,
            side_setbacks=5.0,
        )
        assert result.feasible is False
        assert len(result.failures) == 1


class TestBothFailures:
    """Both checks fail -- two failures, two mitigations."""

    def test_narrow_lot_narrow_clearance(self):
        result = check_panel_fit(
            buildable_envelope=_rect_envelope(6.0, 40.0),
            classified_edges=_DUMMY_EDGES,
            side_setbacks=2.0,
        )
        assert result.feasible is False
        assert len(result.failures) == 2
        assert len(result.mitigations) == 2
        assert any("Crane" in m for m in result.mitigations)
        assert any("Custom" in m for m in result.mitigations)

    def test_empty_envelope_zero_clearance(self):
        result = check_panel_fit(
            buildable_envelope=_empty_envelope(),
            classified_edges=_DUMMY_EDGES,
            side_setbacks=0.0,
        )
        assert result.feasible is False
        assert len(result.failures) == 2
        assert result.min_side_clearance == 0.0
        assert result.min_envelope_width == 0.0
