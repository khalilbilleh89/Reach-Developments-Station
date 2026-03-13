"""create payment plan tables

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-13

Creates the payment-plan persistence layer:
  payment_plan_templates
  payment_schedules

Indexes
-------
  payment_schedules.contract_id — frequent lookup by contract
  payment_schedules.due_date    — cashflow ordering
  payment_schedules.status      — filtering by schedule status

FK relationships
----------------
  payment_schedules.contract_id → sales_contracts.id  (CASCADE)
  payment_schedules.template_id → payment_plan_templates.id  (SET NULL)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "payment_plan_templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("plan_type", sa.String(50), nullable=False),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("down_payment_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("number_of_installments", sa.Integer, nullable=False),
        sa.Column("installment_frequency", sa.String(50), nullable=False),
        sa.Column("handover_percent", sa.Numeric(5, 2), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "payment_schedules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "contract_id",
            sa.String(36),
            sa.ForeignKey("sales_contracts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "template_id",
            sa.String(36),
            sa.ForeignKey("payment_plan_templates.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("installment_number", sa.Integer, nullable=False),
        sa.Column("due_date", sa.Date, nullable=False),
        sa.Column("due_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("notes", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_payment_schedules_contract_id", "payment_schedules", ["contract_id"])
    op.create_index("ix_payment_schedules_due_date", "payment_schedules", ["due_date"])
    op.create_index("ix_payment_schedules_status", "payment_schedules", ["status"])
    op.create_index("ix_payment_schedules_template_id", "payment_schedules", ["template_id"])


def downgrade() -> None:
    op.drop_index("ix_payment_schedules_template_id", table_name="payment_schedules")
    op.drop_index("ix_payment_schedules_status", table_name="payment_schedules")
    op.drop_index("ix_payment_schedules_due_date", table_name="payment_schedules")
    op.drop_index("ix_payment_schedules_contract_id", table_name="payment_schedules")
    op.drop_table("payment_schedules")
    op.drop_table("payment_plan_templates")
