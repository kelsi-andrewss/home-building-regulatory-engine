"""Add rule versioning columns and design_standards table

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-04
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "rule_fragments",
        sa.Column("effective_date", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "rule_fragments",
        sa.Column(
            "superseded_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("rule_fragments.id"),
            nullable=True,
        ),
    )
    op.add_column(
        "rule_fragments",
        sa.Column(
            "variance_available",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )

    op.create_table(
        "design_standards",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("zone_applicability", postgresql.JSON(), nullable=False),
        sa.Column("specific_plan", sa.String(), nullable=True),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("requirement_text", sa.Text(), nullable=False),
        sa.Column("source_document", sa.String(), nullable=False),
        sa.Column("source_section", sa.String(), nullable=True),
        sa.Column("confidence", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_design_standards_category", "design_standards", ["category"]
    )
    op.create_index(
        "ix_design_standards_confidence", "design_standards", ["confidence"]
    )


def downgrade() -> None:
    op.drop_table("design_standards")
    op.drop_column("rule_fragments", "variance_available")
    op.drop_column("rule_fragments", "superseded_by")
    op.drop_column("rule_fragments", "effective_date")
