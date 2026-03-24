"""add concept design tables

Revision ID: 0050
Revises: 0049
Create Date: 2026-03-24

PR-CONCEPT-052 — Concept Design Program Engine Skeleton

Changes
-------
concept_options
  New table. Stores one concept design option (physical program scheme)
  per row.  project_id and scenario_id are both optional FK references,
  consistent with the pre-project lifecycle pattern used by
  feasibility_runs.

concept_unit_mix_lines
  New table. Normalised unit-type rows inside a concept option.
  All aggregate metrics (unit_count, sellable_area, efficiency_ratio)
  are derived from these rows by the concept engine at query time — they
  are never persisted on concept_options.

No destructive changes. Existing tables are unmodified.

Migration Required: Yes
Backfill Required: No
Destructive Change: No
Rollback Safe: Yes
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0050"
down_revision: Union[str, None] = "0049"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "concept_options",
        sa.Column("id", sa.String(36), nullable=False, primary_key=True),
        sa.Column("project_id", sa.String(36), nullable=True),
        sa.Column("scenario_id", sa.String(36), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="draft"),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("site_area", sa.Numeric(16, 2), nullable=True),
        sa.Column("gross_floor_area", sa.Numeric(16, 2), nullable=True),
        sa.Column("building_count", sa.Integer, nullable=True),
        sa.Column("floor_count", sa.Integer, nullable=True),
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
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["scenario_id"],
            ["scenarios.id"],
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        "ix_concept_options_project_id",
        "concept_options",
        ["project_id"],
    )
    op.create_index(
        "ix_concept_options_scenario_id",
        "concept_options",
        ["scenario_id"],
    )

    op.create_table(
        "concept_unit_mix_lines",
        sa.Column("id", sa.String(36), nullable=False, primary_key=True),
        sa.Column("concept_option_id", sa.String(36), nullable=False),
        sa.Column("unit_type", sa.String(100), nullable=False),
        sa.Column("units_count", sa.Integer, nullable=False),
        sa.Column("avg_internal_area", sa.Numeric(12, 2), nullable=True),
        sa.Column("avg_sellable_area", sa.Numeric(12, 2), nullable=True),
        sa.Column("mix_percentage", sa.Numeric(8, 4), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["concept_option_id"],
            ["concept_options.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_concept_unit_mix_lines_concept_option_id",
        "concept_unit_mix_lines",
        ["concept_option_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_concept_unit_mix_lines_concept_option_id",
        table_name="concept_unit_mix_lines",
    )
    op.drop_table("concept_unit_mix_lines")

    op.drop_index("ix_concept_options_scenario_id", table_name="concept_options")
    op.drop_index("ix_concept_options_project_id", table_name="concept_options")
    op.drop_table("concept_options")
