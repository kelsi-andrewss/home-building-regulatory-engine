from __future__ import annotations

from dataclasses import dataclass, field

from backend.app.engine.rule_engine import Confidence, ResolvedConstraint

# CA Gov. Code SS65852.2 state law floor constants
ADU_SETBACK_MAX = 4.0
ADU_HEIGHT_BASE = 16.0
ADU_HEIGHT_TRANSIT = 18.0
ADU_HEIGHT_ATTACHED = 25.0
ADU_SIZE_FLOOR = 800.0
ADU_SIZE_MAX_DETACHED = 1200.0

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
        state_height = ADU_HEIGHT_ATTACHED
    elif near_transit:
        state_height = ADU_HEIGHT_TRANSIT
    else:
        state_height = ADU_HEIGHT_BASE

    result_constraints: list[ResolvedConstraint] = []
    preemptions: list[str] = []

    seen_types: set[str] = set()

    for local in local_constraints:
        ct = local.constraint_type
        seen_types.add(ct)

        if ct in ("setback_side", "setback_rear"):
            # State says city can't require MORE than 4'. If local > 4', override.
            if local.value > ADU_SETBACK_MAX:
                preemptions.append(
                    f"{ct}: local {local.value}' -> state max {ADU_SETBACK_MAX}' "
                    f"(local was more restrictive)"
                )
                result_constraints.append(ResolvedConstraint(
                    constraint_type=ct,
                    value=ADU_SETBACK_MAX,
                    unit="ft",
                    confidence=Confidence.VERIFIED,
                    citation=_CITATION,
                    explanation=f"State law caps ADU {ct} at {ADU_SETBACK_MAX}'",
                    source="adu_state_law",
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
                ))
            else:
                result_constraints.append(local)

        else:
            result_constraints.append(local)

    # Add guaranteed size constraints if not already present
    if "size_min" not in seen_types:
        result_constraints.append(ResolvedConstraint(
            constraint_type="size_min",
            value=ADU_SIZE_FLOOR,
            unit="sf",
            confidence=Confidence.VERIFIED,
            citation=_CITATION,
            explanation=f"State law guarantees {ADU_SIZE_FLOOR} sf minimum ADU",
            source="adu_state_law",
        ))

    if "size_max_detached" not in seen_types:
        result_constraints.append(ResolvedConstraint(
            constraint_type="size_max_detached",
            value=ADU_SIZE_MAX_DETACHED,
            unit="sf",
            confidence=Confidence.VERIFIED,
            citation=_CITATION,
            explanation=f"State law allows up to {ADU_SIZE_MAX_DETACHED} sf detached ADU",
            source="adu_state_law",
        ))

    return ADUPreemptionResult(
        constraints=result_constraints,
        preemptions_applied=preemptions,
    )
