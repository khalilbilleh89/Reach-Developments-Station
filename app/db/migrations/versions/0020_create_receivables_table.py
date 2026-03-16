"""create receivables table

Revision ID: 0020
Revises: 0019
Create Date: 2026-03-16

Adds the receivables ledger table — one record per payment installment.

This table is the Receivables Foundation (PR030). It tracks each installment
amount as a collectible financial obligation with balance and lifecycle status.

Key design decisions:
  - One receivable per installment enforced by a unique constraint on installment_id.
  - balance_due is maintained by the service layer (amount_due - amount_paid),
    not as a computed/generated column, to keep cross-DB compatibility.
  - Non-negative check constraints on monetary fields (all DB engines).
  - Indexes on contract_id, due_date, and status for common query patterns.
  - Status values: pending, due, overdue, partially_paid, paid, cancelled.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_STATUS_VALUES = "('pending', 'due', 'overdue', 'partially_paid', 'paid', 'cancelled')"


def upgrade() -> None:
    op.create_table(
        "receivables",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "contract_id",
            sa.String(36),
            sa.ForeignKey("sales_contracts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "payment_plan_id",
            sa.String(36),
            sa.ForeignKey("payment_plan_templates.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "installment_id",
            sa.String(36),
            sa.ForeignKey("payment_schedules.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("receivable_number", sa.Integer, nullable=False),
        sa.Column("due_date", sa.Date, nullable=False),
        sa.Column("amount_due", sa.Numeric(14, 2), nullable=False),
        sa.Column("amount_paid", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("balance_due", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, server_default="AED"),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    # Indexes for common query patterns
    op.create_index("ix_receivables_contract_id", "receivables", ["contract_id"])
    op.create_index("ix_receivables_payment_plan_id", "receivables", ["payment_plan_id"])
    op.create_index("ix_receivables_installment_id", "receivables", ["installment_id"])
    op.create_index("ix_receivables_due_date", "receivables", ["due_date"])
    op.create_index("ix_receivables_status", "receivables", ["status"])

    # Check constraints for data integrity
    op.create_check_constraint(
        "ck_receivables_status",
        "receivables",
        f"status IN {_STATUS_VALUES}",
    )
    op.create_check_constraint(
        "ck_receivables_amount_due_non_negative",
        "receivables",
        "amount_due >= 0",
    )
    op.create_check_constraint(
        "ck_receivables_amount_paid_non_negative",
        "receivables",
        "amount_paid >= 0",
    )
    op.create_check_constraint(
        "ck_receivables_balance_due_non_negative",
        "receivables",
        "balance_due >= 0",
    )


def downgrade() -> None:
    op.drop_index("ix_receivables_status", table_name="receivables")
    op.drop_index("ix_receivables_due_date", table_name="receivables")
    op.drop_index("ix_receivables_installment_id", table_name="receivables")
    op.drop_index("ix_receivables_payment_plan_id", table_name="receivables")
    op.drop_index("ix_receivables_contract_id", table_name="receivables")
    op.drop_table("receivables")
