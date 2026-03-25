"""add concept option constraint fields

Revision ID: 0052
Revises: 0051
Create Date: 2026-03-25

PR-CONCEPT-059 — FAR, Zoning & Density Validation

Changes
-------
concept_options
  far_limit      NUMERIC(8,4),  nullable  — maximum floor area ratio
  density_limit  NUMERIC(10,2), nullable  — maximum density (dwellings/hectare)

Both columns are optional so that existing concept options remain valid.
Validation rules that depend on these fields are silently skipped when
either value is absent.

Migration Required: Yes
Backfill Required: No
Destructive Change: No
Rollback Safe: Yes
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0052"
down_revision: Union[str, None] = "0051"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "concept_options",
        sa.Column(
            "far_limit",
            sa.Numeric(8, 4),
            nullable=True,
        ),
    )
    op.add_column(
        "concept_options",
        sa.Column(
            "density_limit",
            sa.Numeric(10, 2),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("concept_options", "density_limit")
    op.drop_column("concept_options", "far_limit")
