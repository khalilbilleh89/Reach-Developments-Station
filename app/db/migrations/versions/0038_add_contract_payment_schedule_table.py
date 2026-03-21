"""add contract payment schedule table

Revision ID: 0038
Revises: 0037
Create Date: 2026-03-21

PR-16 — Contract Payment Schedule Engine
PR-16A — Contract Payment Schedule Integrity Hardening

Creates the ``contract_payment_schedule`` table — structured installment
obligations generated when a sales contract is activated.

Columns:

  id                   — UUID primary key.
  contract_id          — FK to sales_contracts.id (CASCADE).
  installment_number   — Sequential position of the installment (1-based).
  due_date             — Calendar date when payment is expected.
  amount               — Installment amount (absolute, not percentage).
  currency             — Currency code (default AED).
  status               — Payment status: pending | paid | overdue | cancelled.
  paid_at              — Timestamp when the payment was recorded (nullable).
  payment_reference    — External reference / receipt number (nullable).
  created_at           — UTC creation timestamp.
  updated_at           — UTC last-update timestamp.

Indexes (auto-named by SQLAlchemy/Alembic):
  index on contract_id    — fast lookups by contract.
  index on due_date       — supports overdue-sweep queries.
  index on status         — supports status-filtered queries.

Constraints:
  uq_cps_contract_installment — unique (contract_id, installment_number)
    prevents duplicate schedule generation at the database level.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0038"
down_revision: Union[str, None] = "0037"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "contract_payment_schedule",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column(
            "contract_id",
            sa.String(36),
            sa.ForeignKey("sales_contracts.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("installment_number", sa.Integer, nullable=False),
        sa.Column("due_date", sa.Date, nullable=False, index=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column(
            "currency",
            sa.String(10),
            nullable=False,
            server_default=sa.text("'AED'"),
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'pending'"),
            index=True,
        ),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payment_reference", sa.String(255), nullable=True),
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
        sa.UniqueConstraint(
            "contract_id",
            "installment_number",
            name="uq_cps_contract_installment",
        ),
    )


def downgrade() -> None:
    op.drop_table("contract_payment_schedule")
