import enum
import uuid
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class ConfidenceLevel(str, enum.Enum):
    VERIFIED = "verified"
    INTERPRETED = "interpreted"
    UNKNOWN = "unknown"


class Base(DeclarativeBase):
    pass


class Parcel(Base):
    __tablename__ = "parcels"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    apn: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    ain: Mapped[str | None] = mapped_column(String, nullable=True)
    address: Mapped[str | None] = mapped_column(String, nullable=True)
    geometry = mapped_column(Geometry("MULTIPOLYGON", srid=4326), nullable=True)
    lot_area_sf: Mapped[float | None] = mapped_column(Float, nullable=True)
    lot_width_ft: Mapped[float | None] = mapped_column(Float, nullable=True)
    year_built: Mapped[int | None] = mapped_column(Integer, nullable=True)
    existing_units: Mapped[int | None] = mapped_column(Integer, nullable=True)
    existing_sqft: Mapped[float | None] = mapped_column(Float, nullable=True)
    use_type: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_api_response = mapped_column(JSON, nullable=True)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    zones: Mapped[list["Zone"]] = relationship(back_populates="parcel")
    assessments: Mapped[list["Assessment"]] = relationship(back_populates="parcel")

    # GeoAlchemy2 auto-creates spatial index on geometry columns


class Zone(Base):
    __tablename__ = "zones"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    parcel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("parcels.id"), nullable=False
    )
    zone_complete: Mapped[str] = mapped_column(String, nullable=False)
    zone_class: Mapped[str] = mapped_column(String, index=True, nullable=False)
    height_district: Mapped[str] = mapped_column(String, nullable=False)
    general_plan_land_use: Mapped[str | None] = mapped_column(String, nullable=True)
    specific_plan_name: Mapped[str | None] = mapped_column(String, nullable=True)
    historic_overlay: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_api_response = mapped_column(JSON, nullable=True)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    parcel: Mapped["Parcel"] = relationship(back_populates="zones")
    assessments: Mapped[list["Assessment"]] = relationship(back_populates="zone")


class RuleFragment(Base):
    __tablename__ = "rule_fragments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    source_document: Mapped[str] = mapped_column(String, nullable=False)
    source_url: Mapped[str | None] = mapped_column(String, nullable=True)
    source_section: Mapped[str | None] = mapped_column(String, nullable=True)
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    zone_applicability = mapped_column(JSON, nullable=False)
    specific_plan: Mapped[str | None] = mapped_column(String, nullable=True)
    constraint_type: Mapped[str] = mapped_column(String, index=True, nullable=False)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    value_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit: Mapped[str | None] = mapped_column(String, nullable=True)
    condition: Mapped[str | None] = mapped_column(String, nullable=True)
    overrides_base_zone: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    confidence: Mapped[str] = mapped_column(String, index=True, nullable=False)
    extraction_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    effective_date: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rule_fragments.id"), nullable=True
    )
    variance_available: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )


class DesignStandard(Base):
    __tablename__ = "design_standards"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    zone_applicability = mapped_column(JSON, nullable=False)
    specific_plan: Mapped[str | None] = mapped_column(String, nullable=True)
    category: Mapped[str] = mapped_column(String, index=True, nullable=False)
    requirement_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_document: Mapped[str] = mapped_column(String, nullable=False)
    source_section: Mapped[str | None] = mapped_column(String, nullable=True)
    confidence: Mapped[str] = mapped_column(String, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )


class SpecificPlan(Base):
    __tablename__ = "specific_plans"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    geometry = mapped_column(Geometry("MULTIPOLYGON", srid=4326), nullable=True)
    source_pdf_url: Mapped[str | None] = mapped_column(String, nullable=True)
    ingestion_status: Mapped[str] = mapped_column(
        String, default="pending", server_default="pending", nullable=False
    )
    fragment_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    ingested_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    # GeoAlchemy2 auto-creates spatial index on geometry columns


class Assessment(Base):
    __tablename__ = "assessments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    parcel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("parcels.id"), nullable=False
    )
    zone_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("zones.id"), nullable=False
    )
    request_address: Mapped[str | None] = mapped_column(String, nullable=True)
    request_apn: Mapped[str | None] = mapped_column(String, nullable=True)
    result = mapped_column(JSON, nullable=False)
    setback_geometry = mapped_column(
        Geometry("POLYGON", srid=4326), nullable=True
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    parcel: Mapped["Parcel"] = relationship(back_populates="assessments")
    zone: Mapped["Zone"] = relationship(back_populates="assessments")

    # GeoAlchemy2 auto-creates spatial index on geometry columns
