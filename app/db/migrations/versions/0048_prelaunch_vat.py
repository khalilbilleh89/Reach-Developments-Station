"""Retain explicit Pre-Launch net and VAT inputs without restating legacy cash."""

import sqlalchemy as sa
from alembic import op

revision = "0048_prelaunch_vat"
down_revision = "0047_company_documents"
branch_labels = None
depends_on = None

TABLE = "cashflow_development_movements"


def upgrade() -> None:
    op.add_column(TABLE, sa.Column("amount_ex_vat", sa.Numeric(18, 2), nullable=True))
    op.add_column(TABLE, sa.Column("vat_rate_percent", sa.Numeric(7, 4), nullable=True))
    op.create_check_constraint(
        op.f("ck_cashflow_development_movements_vat_total_valid"),
        TABLE,
        "(amount_ex_vat IS NULL AND vat_rate_percent IS NULL) OR "
        "(amount_ex_vat IS NOT NULL AND vat_rate_percent IS NOT NULL "
        "AND amount_ex_vat > 0 AND vat_rate_percent BETWEEN 0 AND 100 "
        "AND amount = amount_ex_vat + round(amount_ex_vat * vat_rate_percent / 100, 2))",
    )


def downgrade() -> None:
    if op.get_bind().scalar(
        sa.text(f"SELECT EXISTS (SELECT 1 FROM {TABLE} WHERE amount_ex_vat IS NOT NULL)")
    ):
        raise RuntimeError("Retained expense VAT breakdowns prevent downgrade; roll forward.")
    op.drop_constraint(
        op.f("ck_cashflow_development_movements_vat_total_valid"), TABLE, type_="check"
    )
    op.drop_column(TABLE, "vat_rate_percent")
    op.drop_column(TABLE, "amount_ex_vat")
