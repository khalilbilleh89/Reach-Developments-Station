"""Itemized land acquisition inputs and annual market assumptions.

Revision ID: 0022_land_analytics
Revises: 0021_sales_negotiated_price
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022_land_analytics"
down_revision: str | Sequence[str] | None = "0021_sales_negotiated_price"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "land_parcels",
        sa.Column(
            "acquisition_tax_rate_fraction", sa.Numeric(9, 6), nullable=True, server_default="0"
        ),
    )
    for field in ("agent_fee_amount", "legal_fee_amount", "registration_fee_amount"):
        op.add_column(
            "land_parcels", sa.Column(field, sa.Numeric(18, 2), nullable=True, server_default="0")
        )
    op.add_column(
        "land_parcels", sa.Column("expected_gdv_amount", sa.Numeric(18, 2), nullable=True)
    )
    op.create_check_constraint(
        op.f("ck_land_parcels_acquisition_tax_range"),
        "land_parcels",
        "acquisition_tax_rate_fraction IS NULL OR acquisition_tax_rate_fraction BETWEEN 0 AND 1",
    )
    for field in (
        "agent_fee_amount",
        "legal_fee_amount",
        "registration_fee_amount",
        "expected_gdv_amount",
    ):
        op.create_check_constraint(
            op.f(f"ck_land_parcels_{field}_nonneg"),
            "land_parcels",
            f"{field} IS NULL OR {field} >= 0",
        )
    op.create_table(
        "land_market_assumptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("parcel_id", sa.Uuid(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("change_rate_fraction", sa.Numeric(9, 6), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_land_market_assumptions")),
        sa.ForeignKeyConstraint(
            ["parcel_id"],
            ["land_parcels.id"],
            ondelete="RESTRICT",
            name=op.f("fk_land_market_assumptions_parcel_id_land_parcels"),
        ),
        sa.UniqueConstraint(
            "parcel_id", "year", name=op.f("uq_land_market_assumptions_parcel_id_year")
        ),
        sa.CheckConstraint(
            "year BETWEEN 1900 AND 2200", name=op.f("ck_land_market_assumptions_year_range")
        ),
        sa.CheckConstraint(
            "change_rate_fraction BETWEEN -1 AND 10",
            name=op.f("ck_land_market_assumptions_change_range"),
        ),
    )


def downgrade() -> None:
    op.drop_table("land_market_assumptions")
    op.drop_constraint(op.f("ck_land_parcels_acquisition_tax_range"), "land_parcels", type_="check")
    for field in (
        "agent_fee_amount",
        "legal_fee_amount",
        "registration_fee_amount",
        "expected_gdv_amount",
    ):
        op.drop_constraint(op.f(f"ck_land_parcels_{field}_nonneg"), "land_parcels", type_="check")
        op.drop_column("land_parcels", field)
    op.drop_column("land_parcels", "acquisition_tax_rate_fraction")
