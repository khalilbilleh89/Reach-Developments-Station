"""create construction tables

Revision ID: 0026
Revises: 0025
Create Date: 2026-03-18

PR-C1 — Construction Module

Creates the two tables that support the initial Construction vertical slice:
  - construction_scopes     (links to project / phase / building)
  - construction_milestones (sequenced milestones within a scope)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0026"
down_revision: Union[str, None] = "0025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "construction_scopes",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("phase_id", sa.String(36), sa.ForeignKey("phases.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("building_id", sa.String(36), sa.ForeignKey("buildings.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="planned"),
        sa.Column("start_date", sa.Date, nullable=True),
        sa.Column("target_end_date", sa.Date, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "phase_id", "building_id", name="uq_construction_scope"),
    )

    op.create_table(
        "construction_milestones",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("scope_id", sa.String(36), sa.ForeignKey("construction_scopes.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("sequence", sa.Integer, nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("target_date", sa.Date, nullable=True),
        sa.Column("completion_date", sa.Date, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("scope_id", "sequence", name="uq_milestone_scope_sequence"),
    )


def downgrade() -> None:
    op.drop_table("construction_milestones")
    op.drop_table("construction_scopes")
