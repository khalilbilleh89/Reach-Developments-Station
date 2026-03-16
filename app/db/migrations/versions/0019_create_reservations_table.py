"""create unit_reservations table

Revision ID: 0019
Revises: 0018
Create Date: 2026-03-16

Adds the unit_reservations table — direct unit reservation management.

This table supports the Reservation Pipeline (PR027) which enables sales teams
to place temporary holds on units before a full sales contract is executed.

Key design decisions:
  - Customer contact information (name, phone, email) is stored inline rather
    than referencing a separate Buyer entity, allowing lightweight reservations
    without a full buyer-registration workflow.
  - One ACTIVE reservation per unit is enforced at the service layer and, on
    PostgreSQL, by a partial unique index (WHERE status = 'active').
  - The status column uses a CHECK constraint (enforced on all engines) to
    restrict values to the defined lifecycle states.
  - This table is SEPARATE from the sales-module 'reservations' table which
    is part of the formal buyer/contract workflow.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "unit_reservations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "unit_id",
            sa.String(36),
            sa.ForeignKey("units.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("customer_name", sa.String(200), nullable=False),
        sa.Column("customer_phone", sa.String(50), nullable=False),
        sa.Column("customer_email", sa.String(254), nullable=True),
        sa.Column("reservation_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("reservation_fee", sa.Numeric(14, 2), nullable=True),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_index("ix_unit_reservations_unit_id", "unit_reservations", ["unit_id"])

    op.create_check_constraint(
        "ck_unit_reservations_status",
        "unit_reservations",
        "status IN ('active', 'expired', 'cancelled', 'converted')",
    )

    # PostgreSQL-only: one active reservation per unit at the DB layer.
    # SQLite does not support partial unique indexes; service-layer checks
    # enforce this constraint in the test environment.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.create_index(
            "uq_unit_reservations_active_unit_id",
            "unit_reservations",
            ["unit_id"],
            unique=True,
            postgresql_where=sa.text("status = 'active'"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.drop_index(
            "uq_unit_reservations_active_unit_id",
            table_name="unit_reservations",
        )

    op.drop_index("ix_unit_reservations_unit_id", table_name="unit_reservations")
    op.drop_table("unit_reservations")
