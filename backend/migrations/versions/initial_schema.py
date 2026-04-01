"""Initial schema: parcels, zones, rule_fragments, specific_plans, assessments

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-04-01
"""
from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry

revision = "a1b2c3d4e5f6"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    # --- parcels ---
    op.create_table(
        "parcels",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("apn", sa.String(), nullable=False),
        sa.Column("ain", sa.String(), nullable=True),
        sa.Column("address", sa.String(), nullable=True),
        sa.Column("geometry", Geometry("MULTIPOLYGON", srid=4326), nullable=True),
        sa.Column("lot_area_sf", sa.Float(), nullable=True),
        sa.Column("lot_width_ft", sa.Float(), nullable=True),
        sa.Column("year_built", sa.Integer(), nullable=True),
        sa.Column("existing_units", sa.Integer(), nullable=True),
        sa.Column("existing_sqft", sa.Float(), nullable=True),
        sa.Column("use_type", sa.String(), nullable=True),
        sa.Column("raw_api_response", sa.dialects.postgresql.JSON(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("apn", name="uq_parcels_apn"),
    )
    op.create_index("ix_parcels_apn", "parcels", ["apn"])
    op.create_index("idx_parcels_geometry", "parcels", ["geometry"], postgresql_using="gist")

    # --- zones ---
    op.create_table(
        "zones",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("parcel_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("parcels.id"), nullable=False),
        sa.Column("zone_complete", sa.String(), nullable=False),
        sa.Column("zone_class", sa.String(), nullable=False),
        sa.Column("height_district", sa.String(), nullable=False),
        sa.Column("general_plan_land_use", sa.String(), nullable=True),
        sa.Column("specific_plan_name", sa.String(), nullable=True),
        sa.Column("historic_overlay", sa.String(), nullable=True),
        sa.Column("raw_api_response", sa.dialects.postgresql.JSON(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_zones_zone_class", "zones", ["zone_class"])

    # --- rule_fragments ---
    op.create_table(
        "rule_fragments",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("source_document", sa.String(), nullable=False),
        sa.Column("source_url", sa.String(), nullable=True),
        sa.Column("source_section", sa.String(), nullable=True),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("zone_applicability", sa.dialects.postgresql.JSON(), nullable=False),
        sa.Column("specific_plan", sa.String(), nullable=True),
        sa.Column("constraint_type", sa.String(), nullable=False),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("value_text", sa.Text(), nullable=True),
        sa.Column("unit", sa.String(), nullable=True),
        sa.Column("condition", sa.String(), nullable=True),
        sa.Column("overrides_base_zone", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("confidence", sa.String(), nullable=False),
        sa.Column("extraction_reasoning", sa.Text(), nullable=True),
        sa.Column("extracted_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_rule_fragments_constraint_type", "rule_fragments", ["constraint_type"])
    op.create_index("ix_rule_fragments_confidence", "rule_fragments", ["confidence"])

    # --- specific_plans ---
    op.create_table(
        "specific_plans",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("geometry", Geometry("MULTIPOLYGON", srid=4326), nullable=True),
        sa.Column("source_pdf_url", sa.String(), nullable=True),
        sa.Column("ingestion_status", sa.String(), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("fragment_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("ingested_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("name", name="uq_specific_plans_name"),
    )
    op.create_index("idx_specific_plans_geometry", "specific_plans", ["geometry"], postgresql_using="gist")

    # --- assessments ---
    op.create_table(
        "assessments",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("parcel_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("parcels.id"), nullable=False),
        sa.Column("zone_id", sa.dialects.postgresql.UUID(as_uuid=True), sa.ForeignKey("zones.id"), nullable=False),
        sa.Column("request_address", sa.String(), nullable=True),
        sa.Column("request_apn", sa.String(), nullable=True),
        sa.Column("result", sa.dialects.postgresql.JSON(), nullable=False),
        sa.Column("setback_geometry", Geometry("POLYGON", srid=4326), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_assessments_setback_geometry", "assessments", ["setback_geometry"], postgresql_using="gist")


def downgrade() -> None:
    op.drop_table("assessments")
    op.drop_table("specific_plans")
    op.drop_table("rule_fragments")
    op.drop_table("zones")
    op.drop_table("parcels")
    op.execute("DROP EXTENSION IF EXISTS postgis")
