import uuid
from typing import Literal

from pydantic import BaseModel, model_validator


class AssessRequest(BaseModel):
    address: str | None = None
    apn: str | None = None
    bedrooms: int | None = None
    bathrooms: float | None = None
    sqft: float | None = None

    @model_validator(mode="after")
    def require_address_or_apn(self) -> "AssessRequest":
        if not self.address and not self.apn:
            raise ValueError("At least one of address or apn must be provided")
        return self


class Constraint(BaseModel):
    name: str
    value: str
    confidence: Literal["verified", "interpreted", "unknown"]
    citation: str
    explanation: str
    design_standards: bool = False
    variance_available: bool = False
    conflict_notes: str | None = None


class ConflictNote(BaseModel):
    constraint_name: str
    note: str
    citation: str


class BuildingTypeAssessment(BaseModel):
    type: str
    allowed: bool
    confidence: Literal["verified", "interpreted", "unknown"]
    constraints: list[Constraint]
    max_buildable_area_sf: float | None = None
    max_units: int | None = None


class ZoningData(BaseModel):
    zone_complete: str
    zone_class: str
    height_district: str
    general_plan_land_use: str
    specific_plan: str | None = None
    historic_overlay: str | None = None


class ParcelData(BaseModel):
    apn: str
    address: str
    geometry: dict
    lot_area_sf: float
    lot_width_ft: float | None = None
    year_built: int | None = None
    existing_units: int | None = None
    existing_sqft: float | None = None


class AssessmentResponse(BaseModel):
    parcel: ParcelData
    zoning: ZoningData
    building_types: list[BuildingTypeAssessment]
    setback_geometry: dict | None = None
    summary: str
    assessment_id: uuid.UUID
    conflicts: list[ConflictNote] = []


class ParcelResponse(BaseModel):
    parcel: ParcelData
    zoning: ZoningData


class ChatRequest(BaseModel):
    assessment_id: uuid.UUID
    message: str


class ChatChunk(BaseModel):
    content: str
    done: bool
