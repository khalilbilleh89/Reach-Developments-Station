"""update floors table schema for full floors domain

Revision ID: 0016
Revises: 0014
Create Date: 2026-03-15

Replaces the minimal floors stub (which had only a `level` integer column)
with the full Floors domain schema:
  - name (required)
  - code (required, unique within building)
  - sequence_number (required, unique within building)
  - level_number (optional)
  - description (optional)
  - status updated to support on_hold

Old unique constraint uq_floor_building_level is dropped and replaced by:
  - uq_floor_building_code
  - uq_floor_building_sequence
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0016"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns (nullable first to avoid issues with existing rows)
    op.add_column("floors", sa.Column("name", sa.String(255), nullable=True))
    op.add_column("floors", sa.Column("code", sa.String(100), nullable=True))
    op.add_column("floors", sa.Column("sequence_number", sa.Integer, nullable=True))
    op.add_column("floors", sa.Column("level_number", sa.Integer, nullable=True))
    op.add_column("floors", sa.Column("description", sa.Text, nullable=True))

    # Back-fill: copy legacy `level` value into the new columns for existing rows.
    # Use the broadest possible condition to ensure every row that is missing
    # any of the required new columns gets filled, regardless of whether the
    # old `name` column was already set.
    op.execute(
        "UPDATE floors SET name = 'Floor ' || CAST(level AS VARCHAR), "
        "code = 'FL-' || CAST(level AS VARCHAR), "
        "sequence_number = level, "
        "level_number = level "
        "WHERE code IS NULL OR sequence_number IS NULL"
    )

    # Make the new required columns non-nullable now that all rows have values
    op.alter_column("floors", "name", nullable=False)
    op.alter_column("floors", "code", nullable=False)
    op.alter_column("floors", "sequence_number", nullable=False)

    # Drop the old unique constraint and add new ones
    op.drop_constraint("uq_floor_building_level", "floors", type_="unique")
    op.create_unique_constraint(
        "uq_floor_building_code", "floors", ["building_id", "code"]
    )
    op.create_unique_constraint(
        "uq_floor_building_sequence", "floors", ["building_id", "sequence_number"]
    )

    # Drop the legacy `level` column
    op.drop_column("floors", "level")


def downgrade() -> None:
    # Re-add `level` column and restore the old constraint
    op.add_column("floors", sa.Column("level", sa.Integer, nullable=True))
    op.execute("UPDATE floors SET level = sequence_number")
    op.alter_column("floors", "level", nullable=False)

    op.drop_constraint("uq_floor_building_code", "floors", type_="unique")
    op.drop_constraint("uq_floor_building_sequence", "floors", type_="unique")
    op.create_unique_constraint(
        "uq_floor_building_level", "floors", ["building_id", "level"]
    )

    op.drop_column("floors", "description")
    op.drop_column("floors", "level_number")
    op.drop_column("floors", "sequence_number")
    op.drop_column("floors", "code")
    op.drop_column("floors", "name")
