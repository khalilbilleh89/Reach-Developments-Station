"""harden unit pricing lifecycle

Revision ID: 0035
Revises: 0034
Create Date: 2026-03-21

PR-12 — Pricing Engine Integration Hardening

Hardens the unit_pricing table to support the governed pricing lifecycle:

  1. Drops the UNIQUE constraint on unit_id so that multiple records per
     unit can coexist, enabling proper pricing history.  The service layer
     enforces the "one active record per unit" invariant at runtime.

  2. Adds ``approved_by`` (nullable) — the identifier of the user who
     approved the pricing record.

  3. Adds ``approval_date`` (nullable) — the UTC timestamp when the pricing
     record was formally approved.

  4. Updates the check constraint on pricing_status to include the new
     canonical states ``submitted`` and ``archived`` while retaining the
     legacy ``reviewed`` state for backward compatibility.

SQLite note: constraint drops/creates are guarded with
``if bind.dialect.name == 'postgresql'`` because SQLite does not support
ALTER TABLE ... DROP CONSTRAINT.  The test suite uses SQLite, building the
schema directly from ORM models (not migrations), so these ops are safe to
skip there.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0035"
down_revision: Union[str, None] = "0034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "postgresql":
        # Drop the old unique constraint on unit_id (enables pricing history).
        op.drop_constraint("uq_unit_pricing_unit_id", "unit_pricing", type_="unique")

        # Drop the old status check constraint before recreating it.
        op.drop_constraint("ck_unit_pricing_status", "unit_pricing", type_="check")

    # Add approval metadata columns (supported on all dialects).
    op.add_column(
        "unit_pricing",
        sa.Column("approved_by", sa.String(255), nullable=True),
    )
    op.add_column(
        "unit_pricing",
        sa.Column("approval_date", sa.DateTime(timezone=True), nullable=True),
    )

    if bind.dialect.name == "postgresql":
        # Recreate status check constraint with the full set of valid statuses.
        op.create_check_constraint(
            "ck_unit_pricing_status",
            "unit_pricing",
            "pricing_status IN ('draft', 'submitted', 'reviewed', 'approved', 'archived')",
        )


def downgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "postgresql":
        op.drop_constraint("ck_unit_pricing_status", "unit_pricing", type_="check")

    op.drop_column("unit_pricing", "approval_date")
    op.drop_column("unit_pricing", "approved_by")

    if bind.dialect.name == "postgresql":
        op.create_check_constraint(
            "ck_unit_pricing_status",
            "unit_pricing",
            "pricing_status IN ('draft', 'reviewed', 'approved')",
        )
        op.create_unique_constraint("uq_unit_pricing_unit_id", "unit_pricing", ["unit_id"])
