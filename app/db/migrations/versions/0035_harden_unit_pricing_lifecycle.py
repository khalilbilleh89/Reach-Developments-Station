"""harden unit pricing lifecycle

Revision ID: 0035
Revises: 0034
Create Date: 2026-03-21

PR-12 / PR-12A — Pricing Engine Integration Hardening

Hardens the unit_pricing table to support the governed pricing lifecycle:

  1. Drops the UNIQUE constraint on unit_id so that multiple records per
     unit can coexist, enabling proper pricing history.  The constraint is
     discovered via reflection to avoid hard-coding the auto-generated name.

  2. Adds a PostgreSQL partial unique index on (unit_id) WHERE
     pricing_status != 'archived'.  This enforces the "one active record
     per unit" invariant at the database level, making it safe under
     concurrent requests.

  3. Adds ``approved_by`` (nullable) — the identifier of the user who
     approved the pricing record.

  4. Adds ``approval_date`` (nullable) — the UTC timestamp when the pricing
     record was formally approved.

  5. Updates the check constraint on pricing_status to include the new
     canonical states ``submitted`` and ``archived`` while retaining the
     legacy ``reviewed`` state for backward compatibility.

SQLite note: constraint drops/creates and partial indexes are guarded with
``if bind.dialect.name == 'postgresql'`` because SQLite does not support
ALTER TABLE ... DROP CONSTRAINT or partial indexes.  The test suite uses
SQLite, building the schema directly from ORM models (not migrations), so
these ops are safe to skip there.
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
        # Discover and drop the auto-generated unique constraint on unit_id.
        # The constraint was created by sa.Column(..., unique=True) without an
        # explicit name, so PostgreSQL auto-names it (typically
        # unit_pricing_unit_id_key).  We reflect the actual name rather than
        # hard-coding it to avoid migration failures.
        inspector = sa.inspect(bind)
        unique_constraints = inspector.get_unique_constraints("unit_pricing")
        unit_id_uc_name = None
        for uc in unique_constraints:
            if (uc.get("column_names") or []) == ["unit_id"]:
                unit_id_uc_name = uc.get("name")
                break
        if unit_id_uc_name:
            op.drop_constraint(unit_id_uc_name, "unit_pricing", type_="unique")
        else:
            # The constraint may have already been dropped in a previous
            # partial upgrade attempt, or may not exist on fresh installs
            # where migration 0017 was not run.  This is safe to skip.
            import warnings
            warnings.warn(
                "Migration 0035: could not find a unique constraint on "
                "unit_pricing.unit_id — it may have already been removed.",
                stacklevel=2,
            )

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

        # Partial unique index: only one non-archived pricing record per unit.
        # This replaces the old UNIQUE(unit_id) constraint and is race-safe.
        op.create_index(
            "uix_unit_pricing_unit_id_active",
            "unit_pricing",
            ["unit_id"],
            unique=True,
            postgresql_where=sa.text("pricing_status != 'archived'"),
        )


def downgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "postgresql":
        op.drop_index("uix_unit_pricing_unit_id_active", table_name="unit_pricing")
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
