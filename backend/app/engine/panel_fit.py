from __future__ import annotations

from dataclasses import dataclass, field

from backend.app.engine.geometry_utils import derive_lot_dimensions

# Cover panel delivery constraints
MIN_SIDE_CLEARANCE_FT = 4.0
MIN_ENVELOPE_WIDTH_FT = 8.0


@dataclass
class PanelFitResult:
    feasible: bool
    min_side_clearance: float
    min_envelope_width: float
    failures: list[str] = field(default_factory=list)
    mitigations: list[str] = field(default_factory=list)


def check_panel_fit(
    buildable_envelope: dict,
    classified_edges: dict,
    side_setbacks: float,
) -> PanelFitResult:
    """Check whether Cover's prefab panels can be delivered and placed.

    Two independent checks:
    1. Side clearance: side_setbacks must be >= MIN_SIDE_CLEARANCE_FT (4').
       Failure mitigation: crane delivery.
    2. Envelope width: MBR shorter edge of buildable_envelope must be
       >= MIN_ENVELOPE_WIDTH_FT (8'). Failure mitigation: custom panels.

    Uses strict < comparison: exactly 4.0 or 8.0 passes.
    """
    failures: list[str] = []
    mitigations: list[str] = []

    # --- Side clearance check ---
    min_side_clearance = side_setbacks

    if min_side_clearance < MIN_SIDE_CLEARANCE_FT:
        failures.append(
            f"Side clearance {min_side_clearance}' < {MIN_SIDE_CLEARANCE_FT}' minimum"
        )
        mitigations.append("Crane delivery required for panel placement")

    # --- Envelope width check ---
    coords = buildable_envelope.get("coordinates", [])
    if not coords or not coords[0]:
        min_envelope_width = 0.0
    else:
        dims = derive_lot_dimensions(buildable_envelope)
        min_envelope_width = dims["width"]

    if min_envelope_width < MIN_ENVELOPE_WIDTH_FT:
        failures.append(
            f"Envelope width {min_envelope_width:.1f}' < {MIN_ENVELOPE_WIDTH_FT}' minimum"
        )
        mitigations.append("Custom-sized panels required")

    return PanelFitResult(
        feasible=len(failures) == 0,
        min_side_clearance=min_side_clearance,
        min_envelope_width=min_envelope_width,
        failures=failures,
        mitigations=mitigations,
    )
