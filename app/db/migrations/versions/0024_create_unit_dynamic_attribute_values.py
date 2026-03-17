"""create unit dynamic attribute values table

Revision ID: 0024
Revises: 0023
Create Date: 2026-03-17

Adds the unit_dynamic_attribute_values table which bridges project-level
attribute options (PR-032) to individual units (PR-033).

Each row stores one selected project-defined option for a unit/definition pair.
The unique constraint on (unit_id, definition_id) enforces one selection per
definition per unit.

Foreign keys:
  unit_id       → units.id            (CASCADE delete)
  definition_id → project_attribute_definitions.id (CASCADE delete)
  option_id     → project_attribute_options.id      (CASCADE delete)

This migration is additive and non-breaking.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0024"
down_revision: Union[str, None] = "0023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "unit_dynamic_attribute_values",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "unit_id",
            sa.String(36),
            sa.ForeignKey("units.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "definition_id",
            sa.String(36),
            sa.ForeignKey("project_attribute_definitions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "option_id",
            sa.String(36),
            sa.ForeignKey("project_attribute_options.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("unit_id", "definition_id", name="uq_udav_unit_definition"),
    )
    op.create_index(
        "ix_unit_dynamic_attribute_values_unit_id",
        "unit_dynamic_attribute_values",
        ["unit_id"],
    )
    op.create_index(
        "ix_unit_dynamic_attribute_values_definition_id",
        "unit_dynamic_attribute_values",
        ["definition_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_unit_dynamic_attribute_values_definition_id",
        table_name="unit_dynamic_attribute_values",
    )
    op.drop_index(
        "ix_unit_dynamic_attribute_values_unit_id",
        table_name="unit_dynamic_attribute_values",
    )
    op.drop_table("unit_dynamic_attribute_values")
