"""add concept land integration fields

Revision ID: 0053
Revises: 0052
Create Date: 2026-03-25

PR-CONCEPT-060 — Land & Scenario Integration for Concept Design

Changes
-------
concept_options
  land_id                    VARCHAR(36), nullable — inherited from scenario's land parcel
  concept_override_far_limit     NUMERIC(8,4), nullable — explicit FAR override
  concept_override_density_limit NUMERIC(10,2), nullable — explicit density override

These columns let the service record which land parcel provided the upstream
constraints and whether the user explicitly overrode FAR or density limits.
Validation uses priority: overrides > scenario land constraints > manual inputs.

No destructive changes. Existing rows remain valid with all three columns NULL.

Migration Required: Yes
Backfill Required: No
Destructive Change: No
Rollback Safe: Yes
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0053"
down_revision: Union[str, None] = "0052"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "concept_options",
        sa.Column(
            "land_id",
            sa.String(36),
            nullable=True,
        ),
    )
    op.add_column(
        "concept_options",
        sa.Column(
            "concept_override_far_limit",
            sa.Numeric(8, 4),
            nullable=True,
        ),
    )
    op.add_column(
        "concept_options",
        sa.Column(
            "concept_override_density_limit",
            sa.Numeric(10, 2),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("concept_options", "concept_override_density_limit")
    op.drop_column("concept_options", "concept_override_far_limit")
    op.drop_column("concept_options", "land_id")
