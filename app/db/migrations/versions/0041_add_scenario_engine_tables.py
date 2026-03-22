"""add scenario engine tables

Revision ID: 0041
Revises: 0040
Create Date: 2026-03-22

PR-ARCH-003 / PR-ARCH-003A — Scenario Engine Core Framework + Integrity Hardening

Creates the canonical Scenario Engine tables.

Tables
------
scenarios
    Central development-option entity.  Can be created against land,
    feasibility, or concept planning contexts.  Tracks lifecycle status
    (draft / approved / archived) and duplication lineage.
    Columns: id, name, code, status, source_type, project_id, land_id,
             base_scenario_id, is_active, notes, created_at, updated_at.

scenario_versions
    Immutable assumption snapshots and comparison-metric snapshots for a
    scenario.  version_number increments per scenario.  Only one version
    per scenario may carry is_approved=True at any time.
    Columns: id, scenario_id, version_number, title, notes,
             assumptions_json, comparison_metrics_json, created_by,
             is_approved, created_at, updated_at.

Indexes and Constraints
-----------------------
  scenarios(code), scenarios(project_id), scenarios(land_id),
  scenarios(base_scenario_id)
  scenario_versions(scenario_id)
  UNIQUE scenario_versions(scenario_id, version_number)
  UNIQUE partial index on scenario_versions(scenario_id) WHERE is_approved=true
    — PostgreSQL only; enforces at most one approved version per scenario.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0041"
down_revision: Union[str, None] = "0040"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # scenarios
    # ------------------------------------------------------------------
    op.create_table(
        "scenarios",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("code", sa.String(100), nullable=True, index=True),
        sa.Column("status", sa.String(50), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("source_type", sa.String(50), nullable=False, server_default=sa.text("'feasibility'")),
        sa.Column("project_id", sa.String(36), nullable=True, index=True),
        sa.Column("land_id", sa.String(36), nullable=True, index=True),
        sa.Column(
            "base_scenario_id",
            sa.String(36),
            sa.ForeignKey("scenarios.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("1")),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # ------------------------------------------------------------------
    # scenario_versions
    # ------------------------------------------------------------------
    op.create_table(
        "scenario_versions",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column(
            "scenario_id",
            sa.String(36),
            sa.ForeignKey("scenarios.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("version_number", sa.Integer, nullable=False, server_default=sa.text("1")),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("assumptions_json", sa.JSON, nullable=True),
        sa.Column("comparison_metrics_json", sa.JSON, nullable=True),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("is_approved", sa.Boolean, nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        # Unique version numbers per scenario — enforced on all dialects.
        sa.UniqueConstraint(
            "scenario_id",
            "version_number",
            name="uq_scenario_versions_scenario_id_version_number",
        ),
    )

    # Partial unique index: at most one approved version per scenario.
    # Only applied on PostgreSQL; SQLite does not support partial indexes and
    # the service layer already enforces this invariant.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.create_index(
            "uq_scenario_versions_approved_per_scenario",
            "scenario_versions",
            ["scenario_id"],
            unique=True,
            postgresql_where=sa.text("is_approved = true"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.drop_index(
            "uq_scenario_versions_approved_per_scenario",
            table_name="scenario_versions",
        )
    op.drop_table("scenario_versions")
    op.drop_table("scenarios")
