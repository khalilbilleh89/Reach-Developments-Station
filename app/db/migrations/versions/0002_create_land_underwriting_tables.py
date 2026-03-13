"""create land underwriting tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-11

Adds the land underwriting tables:
  land_parcels → land_assumptions + land_valuations
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "land_parcels",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parcel_name", sa.String(255), nullable=False),
        sa.Column("parcel_code", sa.String(100), nullable=False),
        sa.Column("country", sa.String(100), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("district", sa.String(100), nullable=True),
        sa.Column("address", sa.String(500), nullable=True),
        sa.Column("land_area_sqm", sa.Numeric(12, 2), nullable=True),
        sa.Column("frontage_m", sa.Numeric(10, 2), nullable=True),
        sa.Column("depth_m", sa.Numeric(10, 2), nullable=True),
        sa.Column("zoning_category", sa.String(100), nullable=True),
        sa.Column("permitted_far", sa.Numeric(6, 3), nullable=True),
        sa.Column("max_height_m", sa.Numeric(8, 2), nullable=True),
        sa.Column("max_floors", sa.Integer, nullable=True),
        sa.Column("corner_plot", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("utilities_available", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("parcel_code", "project_id", name="uq_land_parcel_code_project"),
    )
    op.create_index("ix_land_parcels_project_id", "land_parcels", ["project_id"])

    op.create_table(
        "land_assumptions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("parcel_id", sa.String(36), sa.ForeignKey("land_parcels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_use", sa.String(100), nullable=True),
        sa.Column("expected_sellable_ratio", sa.Numeric(5, 4), nullable=True),
        sa.Column("expected_buildable_area_sqm", sa.Numeric(12, 2), nullable=True),
        sa.Column("expected_sellable_area_sqm", sa.Numeric(12, 2), nullable=True),
        sa.Column("parking_ratio", sa.Numeric(5, 4), nullable=True),
        sa.Column("service_area_ratio", sa.Numeric(5, 4), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_land_assumptions_parcel_id", "land_assumptions", ["parcel_id"])

    op.create_table(
        "land_valuations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("parcel_id", sa.String(36), sa.ForeignKey("land_parcels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scenario_name", sa.String(255), nullable=False),
        sa.Column("scenario_type", sa.String(50), nullable=False),
        sa.Column("assumed_sale_price_per_sqm", sa.Numeric(14, 2), nullable=True),
        sa.Column("assumed_cost_per_sqm", sa.Numeric(14, 2), nullable=True),
        sa.Column("expected_gdv", sa.Numeric(20, 2), nullable=True),
        sa.Column("expected_cost", sa.Numeric(20, 2), nullable=True),
        sa.Column("residual_land_value", sa.Numeric(20, 2), nullable=True),
        sa.Column("land_value_per_sqm", sa.Numeric(14, 2), nullable=True),
        sa.Column("valuation_notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_land_valuations_parcel_id", "land_valuations", ["parcel_id"])


def downgrade() -> None:
    op.drop_table("land_valuations")
    op.drop_table("land_assumptions")
    op.drop_table("land_parcels")
