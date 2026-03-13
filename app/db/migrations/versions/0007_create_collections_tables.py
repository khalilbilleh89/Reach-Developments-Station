"""create collections tables

Revision ID: 0007
Revises: 0006
Create Date: 2026-03-13

Creates the collections persistence layer:
  payment_receipts

Indexes
-------
  payment_receipts.contract_id          — lookup receipts by contract
  payment_receipts.payment_schedule_id  — lookup receipts by schedule line
  payment_receipts.receipt_date         — date-range filtering
  payment_receipts.status               — filter by receipt lifecycle status

FK relationships
----------------
  payment_receipts.contract_id         → sales_contracts.id      (CASCADE)
  payment_receipts.payment_schedule_id → payment_schedules.id    (CASCADE)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "payment_receipts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "contract_id",
            sa.String(36),
            sa.ForeignKey("sales_contracts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "payment_schedule_id",
            sa.String(36),
            sa.ForeignKey("payment_schedules.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("receipt_date", sa.Date, nullable=False),
        sa.Column("amount_received", sa.Numeric(14, 2), nullable=False),
        sa.Column("payment_method", sa.String(50), nullable=True),
        sa.Column("reference_number", sa.String(100), nullable=True),
        sa.Column("notes", sa.String(1000), nullable=True),
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default=sa.text("'recorded'"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_payment_receipts_contract_id", "payment_receipts", ["contract_id"]
    )
    op.create_index(
        "ix_payment_receipts_payment_schedule_id",
        "payment_receipts",
        ["payment_schedule_id"],
    )
    op.create_index(
        "ix_payment_receipts_receipt_date", "payment_receipts", ["receipt_date"]
    )
    op.create_index("ix_payment_receipts_status", "payment_receipts", ["status"])


def downgrade() -> None:
    op.drop_index("ix_payment_receipts_status", table_name="payment_receipts")
    op.drop_index("ix_payment_receipts_receipt_date", table_name="payment_receipts")
    op.drop_index(
        "ix_payment_receipts_payment_schedule_id", table_name="payment_receipts"
    )
    op.drop_index("ix_payment_receipts_contract_id", table_name="payment_receipts")
    op.drop_table("payment_receipts")
