"""Distinguish already-paid contract payments from invoice disbursements."""

import sqlalchemy as sa
from alembic import op

revision = "0033_contract_payments"
down_revision = "0032_building_units"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "construction_payments",
        sa.Column(
            "direct_contract_payment", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )


def downgrade() -> None:
    if op.get_bind().scalar(
        sa.text("SELECT EXISTS (SELECT 1 FROM construction_payments WHERE direct_contract_payment)")
    ):
        raise RuntimeError("Direct contract payment history must be retained; downgrade refused.")
    op.drop_column("construction_payments", "direct_contract_payment")
