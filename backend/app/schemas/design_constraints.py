import uuid
from typing import Literal

from pydantic import BaseModel


class EdgeSetback(BaseModel):
    edge: str
    setback_ft: float
    confidence: Literal["verified", "interpreted", "unknown"]
    citation: str


class HeightEnvelope(BaseModel):
    max_height_ft: float
    confidence: Literal["verified", "interpreted", "unknown"]
    citation: str


class MaterialRequirement(BaseModel):
    requirement: str
    source: str
    confidence: Literal["verified", "interpreted", "unknown"]


class PanelFitResponse(BaseModel):
    feasible: bool
    min_side_clearance_ft: float
    min_envelope_width_ft: float
    failures: list[str]
    mitigations: list[str]


class DesignConstraintResponse(BaseModel):
    assessment_id: uuid.UUID
    parcel_apn: str
    envelope_geojson: dict
    per_edge_setbacks: list[EdgeSetback]
    height_envelope: HeightEnvelope
    material_requirements: list[MaterialRequirement]
    panel_fit: PanelFitResponse
