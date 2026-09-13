"""Per-installment VAT rates; legacy amounts and contract snapshots stay intact."""

import sqlalchemy as sa
from alembic import op

revision = "0026_installment_tax"
down_revision = "0025_prelaunch_master"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "payment_plan_installments", sa.Column("tax_rate_fraction", sa.Numeric(9, 6), nullable=True)
    )
    op.create_check_constraint(
        op.f("ck_payment_plan_installments_tax_rate_range"),
        "payment_plan_installments",
        "tax_rate_fraction IS NULL OR (tax_rate_fraction >= 0 AND tax_rate_fraction <= 1)",
    )
    op.create_check_constraint(
        op.f("ck_payment_plan_installments_tax_rate_amount"),
        "payment_plan_installments",
        "tax_rate_fraction IS NULL OR tax_amount = round(principal_amount * tax_rate_fraction, 2)",
    )
    op.drop_constraint(
        op.f("ck_payment_plan_versions_charge_ok"), "payment_plan_versions", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_payment_plan_versions_charge_ok"),
        "payment_plan_versions",
        "charge_allocation_mode IN ('pro_rata', 'manual', 'per_installment')",
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM payment_plan_versions WHERE "
            "charge_allocation_mode = 'per_installment') OR EXISTS (SELECT 1 FROM "
            "payment_plan_installments WHERE tax_rate_fraction IS NOT NULL)"
        )
    ).scalar():
        raise RuntimeError(
            "Per-installment tax history exists; retain this schema and roll forward."
        )
    op.drop_constraint(
        op.f("ck_payment_plan_versions_charge_ok"), "payment_plan_versions", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_payment_plan_versions_charge_ok"),
        "payment_plan_versions",
        "charge_allocation_mode IN ('pro_rata', 'manual')",
    )
    op.drop_constraint(
        op.f("ck_payment_plan_installments_tax_rate_amount"),
        "payment_plan_installments",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_payment_plan_installments_tax_rate_range"),
        "payment_plan_installments",
        type_="check",
    )
    op.drop_column("payment_plan_installments", "tax_rate_fraction")
