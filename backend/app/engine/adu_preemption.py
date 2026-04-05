from __future__ import annotations

from dataclasses import dataclass, field

from backend.app.engine.rule_engine import Confidence, ResolvedConstraint

# CA Gov. Code SS65852.2 — update when legislation changes
STATE_LAW = {
    "setback_max": 4.0,
    "height_base": 16.0,
    "height_transit": 18.0,
    "height_attached": 25.0,
    "size_floor": 800.0,
    "size_max_detached": 1200.0,
}

_SOURCE = "CA Gov. Code SS65852.2"
_CITATION = "Gov. Code SS65852.2 (AB 68, SB 13, AB 881, SB 897)"


@dataclass
class ADUPreemptionResult:
    constraints: list[ResolvedConstraint]
    preemptions_applied: list[str] = field(default_factory=list)


def apply_adu_preemption(
    local_constraints: list[ResolvedConstraint],
    near_transit: bool = False,
    attached: bool = False,
) -> ADUPreemptionResult:
    """Apply CA state law floors. Override local when local is more restrictive.

    State floors:
    - setback_side/setback_rear: 4' max (local can't require more)
    - height_max: 16' guaranteed, 18' near transit, 25' if attached
    - size_min: 800 sf guaranteed
    - size_max_detached: 1,200 sf

    If local already allows >= state floor, local stands.
    If local is more restrictive, state law preempts.
    """
    if attached:
        state_height = STATE_LAW["height_attached"]
    elif near_transit:
        state_height = STATE_LAW["height_transit"]
    else:
        state_height = STATE_LAW["height_base"]

    result_constraints: list[ResolvedConstraint] = []
    preemptions: list[str] = []

    seen_types: set[str] = set()

    for local in local_constraints:
        ct = local.constraint_type
        seen_types.add(ct)

        if ct in ("setback_side", "setback_rear"):
            # State says city can't require MORE than 4'. If local > 4', override.
            if local.value > STATE_LAW["setback_max"]:
                preemptions.append(
                    f"{ct}: local {local.value}' -> state max {STATE_LAW['setback_max']}' "
                    f"(local was more restrictive)"
                )
                result_constraints.append(ResolvedConstraint(
                    constraint_type=ct,
                    value=STATE_LAW["setback_max"],
                    unit="ft",
                    confidence=Confidence.VERIFIED,
                    citation=_CITATION,
                    explanation=f"State law caps ADU {ct} at {STATE_LAW['setback_max']}'",
                    source="adu_state_law",
                    variance_available=False,
                ))
            else:
                result_constraints.append(local)

        elif ct == "height_max":
            # State says city can't require LESS than state floor.
            # If local < state floor, override to state floor.
            if local.value < state_height:
                preemptions.append(
                    f"height_max: local {local.value}' -> state floor {state_height}' "
                    f"(local was more restrictive)"
                )
                result_constraints.append(ResolvedConstraint(
                    constraint_type="height_max",
                    value=state_height,
                    unit="ft",
                    confidence=Confidence.VERIFIED,
                    citation=_CITATION,
                    explanation=f"State law guarantees ADU height of {state_height}'",
                    source="adu_state_law",
                    variance_available=False,
                ))
            else:
                result_constraints.append(local)

        else:
            result_constraints.append(local)

    # Add guaranteed size constraints if not already present
    if "size_min" not in seen_types:
        result_constraints.append(ResolvedConstraint(
            constraint_type="size_min",
            value=STATE_LAW["size_floor"],
            unit="sf",
            confidence=Confidence.VERIFIED,
            citation=_CITATION,
            explanation=f"State law guarantees {STATE_LAW['size_floor']} sf minimum ADU",
            source="adu_state_law",
            variance_available=False,
        ))

    if "size_max_detached" not in seen_types:
        result_constraints.append(ResolvedConstraint(
            constraint_type="size_max_detached",
            value=STATE_LAW["size_max_detached"],
            unit="sf",
            confidence=Confidence.VERIFIED,
            citation=_CITATION,
            explanation=f"State law allows up to {STATE_LAW['size_max_detached']} sf detached ADU",
            source="adu_state_law",
            variance_available=False,
        ))

    return ADUPreemptionResult(
        constraints=result_constraints,
        preemptions_applied=preemptions,
    )
