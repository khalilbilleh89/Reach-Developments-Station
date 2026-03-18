"""create construction tables

Revision ID: 0026
Revises: 0025
Create Date: 2026-03-18

PR-C1 — Construction Module

Creates the two tables that support the initial Construction vertical slice:
  - construction_scopes     (links to project / phase / building)
  - construction_milestones (sequenced milestones within a scope)

PostgreSQL partial unique indexes are added for each NULL-pattern of the
(project_id, phase_id, building_id) link combination, since a composite
UNIQUE constraint does not enforce uniqueness when any column is NULL
(PostgreSQL treats NULLs as distinct). Each allowed link shape therefore
gets its own partial index, race-safe at the DB level.
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
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True),
        sa.Column("phase_id", sa.String(36), sa.ForeignKey("phases.id", ondelete="CASCADE"), nullable=True),
        sa.Column("building_id", sa.String(36), sa.ForeignKey("buildings.id", ondelete="CASCADE"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("start_date", sa.Date, nullable=True),
        sa.Column("target_end_date", sa.Date, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_construction_scopes_project_id", "construction_scopes", ["project_id"])
    op.create_index("ix_construction_scopes_phase_id", "construction_scopes", ["phase_id"])
    op.create_index("ix_construction_scopes_building_id", "construction_scopes", ["building_id"])

    op.create_table(
        "construction_milestones",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("scope_id", sa.String(36), sa.ForeignKey("construction_scopes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("sequence", sa.Integer, nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("target_date", sa.Date, nullable=True),
        sa.Column("completion_date", sa.Date, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("scope_id", "sequence", name="uq_milestone_scope_sequence"),
    )
    op.create_index("ix_construction_milestones_scope_id", "construction_milestones", ["scope_id"])

    # PostgreSQL partial unique indexes for construction_scopes.
    # A composite UNIQUE(project_id, phase_id, building_id) does not prevent
    # duplicate rows when any column is NULL (each NULL is considered distinct).
    # One partial index per allowed NULL-pattern makes uniqueness race-safe.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # 1. project-only scope
        op.create_index(
            "uq_cs_project_only",
            "construction_scopes",
            ["project_id"],
            unique=True,
            postgresql_where=sa.text("phase_id IS NULL AND building_id IS NULL"),
        )
        # 2. phase-only scope
        op.create_index(
            "uq_cs_phase_only",
            "construction_scopes",
            ["phase_id"],
            unique=True,
            postgresql_where=sa.text("project_id IS NULL AND building_id IS NULL"),
        )
        # 3. building-only scope
        op.create_index(
            "uq_cs_building_only",
            "construction_scopes",
            ["building_id"],
            unique=True,
            postgresql_where=sa.text("project_id IS NULL AND phase_id IS NULL"),
        )
        # 4. project + phase (no building)
        op.create_index(
            "uq_cs_project_phase",
            "construction_scopes",
            ["project_id", "phase_id"],
            unique=True,
            postgresql_where=sa.text("project_id IS NOT NULL AND phase_id IS NOT NULL AND building_id IS NULL"),
        )
        # 5. project + building (no phase)
        op.create_index(
            "uq_cs_project_building",
            "construction_scopes",
            ["project_id", "building_id"],
            unique=True,
            postgresql_where=sa.text("project_id IS NOT NULL AND building_id IS NOT NULL AND phase_id IS NULL"),
        )
        # 6. phase + building (no project)
        op.create_index(
            "uq_cs_phase_building",
            "construction_scopes",
            ["phase_id", "building_id"],
            unique=True,
            postgresql_where=sa.text("phase_id IS NOT NULL AND building_id IS NOT NULL AND project_id IS NULL"),
        )
        # 7. all three non-null (composite index rather than UniqueConstraint)
        op.create_index(
            "uq_cs_project_phase_building",
            "construction_scopes",
            ["project_id", "phase_id", "building_id"],
            unique=True,
            postgresql_where=sa.text("project_id IS NOT NULL AND phase_id IS NOT NULL AND building_id IS NOT NULL"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.drop_index("uq_cs_project_phase_building", table_name="construction_scopes")
        op.drop_index("uq_cs_phase_building", table_name="construction_scopes")
        op.drop_index("uq_cs_project_building", table_name="construction_scopes")
        op.drop_index("uq_cs_project_phase", table_name="construction_scopes")
        op.drop_index("uq_cs_building_only", table_name="construction_scopes")
        op.drop_index("uq_cs_phase_only", table_name="construction_scopes")
        op.drop_index("uq_cs_project_only", table_name="construction_scopes")

    op.drop_index("ix_construction_milestones_scope_id", table_name="construction_milestones")
    op.drop_table("construction_milestones")
    op.drop_index("ix_construction_scopes_building_id", table_name="construction_scopes")
    op.drop_index("ix_construction_scopes_phase_id", table_name="construction_scopes")
    op.drop_index("ix_construction_scopes_project_id", table_name="construction_scopes")
    op.drop_table("construction_scopes")
