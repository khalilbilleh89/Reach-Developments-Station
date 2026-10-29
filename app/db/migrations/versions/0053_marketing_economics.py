"""Sourced unit valuation and explicit rental delay; preserve existing assumptions."""

import sqlalchemy as sa
from alembic import op

revision = "0053_marketing_economics"
down_revision = "0052_design_payments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    table = "marketing_rental_scenarios"
    op.add_column(
        table, sa.Column("rental_delay_months", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column(table, sa.Column("current_value", sa.Numeric(18, 2)))
    op.add_column(table, sa.Column("valuation_source", sa.String(320)))
    op.add_column(table, sa.Column("valuation_as_of", sa.Date()))
    op.create_check_constraint(
        op.f("ck_marketing_rental_scenarios_rental_delay"),
        table,
        "rental_delay_months BETWEEN 0 AND 60",
    )
    op.create_check_constraint(
        op.f("ck_marketing_rental_scenarios_rental_valuation"),
        table,
        "(current_value IS NULL AND valuation_source IS NULL AND valuation_as_of IS NULL) OR "
        "(current_value > 0 AND current_value IS NOT NULL AND unit_id IS NOT NULL "
        "AND valuation_source IS NOT NULL AND valuation_as_of IS NOT NULL)",
    )


def downgrade() -> None:
    table = "marketing_rental_scenarios"
    if op.get_bind().scalar(
        sa.text(
            f"SELECT count(*) FROM {table} "
            "WHERE rental_delay_months <> 0 OR current_value IS NOT NULL"
        )
    ):
        raise RuntimeError("Marketing valuation/delay history must be retained; downgrade refused.")
    op.drop_constraint(op.f("ck_marketing_rental_scenarios_rental_valuation"), table, type_="check")
    op.drop_constraint(op.f("ck_marketing_rental_scenarios_rental_delay"), table, type_="check")
    for column in ("valuation_as_of", "valuation_source", "current_value", "rental_delay_months"):
        op.drop_column(table, column)
