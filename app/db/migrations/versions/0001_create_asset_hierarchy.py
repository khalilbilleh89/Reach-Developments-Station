"""create asset hierarchy tables

Revision ID: 0001
Revises:
Create Date: 2026-03-11

Adds the core asset hierarchy tables:
  projects → phases → buildings → floors → units
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("code", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("location", sa.String(500), nullable=True),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_projects_code", "projects", ["code"])

    op.create_table(
        "phases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("sequence", sa.Integer, nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("start_date", sa.Date, nullable=True),
        sa.Column("end_date", sa.Date, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "sequence", name="uq_phase_project_sequence"),
    )
    op.create_index("ix_phases_project_id", "phases", ["project_id"])

    op.create_table(
        "buildings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("phase_id", sa.String(36), sa.ForeignKey("phases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("floors_count", sa.Integer, nullable=True),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("phase_id", "code", name="uq_building_phase_code"),
    )
    op.create_index("ix_buildings_phase_id", "buildings", ["phase_id"])

    op.create_table(
        "floors",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("building_id", sa.String(36), sa.ForeignKey("buildings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("level", sa.Integer, nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("building_id", "level", name="uq_floor_building_level"),
    )
    op.create_index("ix_floors_building_id", "floors", ["building_id"])

    op.create_table(
        "units",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("floor_id", sa.String(36), sa.ForeignKey("floors.id", ondelete="CASCADE"), nullable=False),
        sa.Column("unit_number", sa.String(50), nullable=False),
        sa.Column("unit_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("internal_area", sa.Numeric(10, 2), nullable=False),
        sa.Column("balcony_area", sa.Numeric(10, 2), nullable=True),
        sa.Column("terrace_area", sa.Numeric(10, 2), nullable=True),
        sa.Column("roof_garden_area", sa.Numeric(10, 2), nullable=True),
        sa.Column("front_garden_area", sa.Numeric(10, 2), nullable=True),
        sa.Column("gross_area", sa.Numeric(10, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("floor_id", "unit_number", name="uq_unit_floor_number"),
    )
    op.create_index("ix_units_floor_id", "units", ["floor_id"])


def downgrade() -> None:
    op.drop_table("units")
    op.drop_table("floors")
    op.drop_table("buildings")
    op.drop_table("phases")
    op.drop_table("projects")
