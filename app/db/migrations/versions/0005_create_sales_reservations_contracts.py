"""create sales reservations contracts

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-13

Creates the sales domain persistence layer:
  buyers
  reservations
  sales_contracts
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "buyers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("phone", sa.String(50), nullable=False),
        sa.Column("nationality", sa.String(100), nullable=True),
        sa.Column("notes", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_buyers_email", "buyers", ["email"])

    op.create_table(
        "reservations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "unit_id",
            sa.String(36),
            sa.ForeignKey("units.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "buyer_id",
            sa.String(36),
            sa.ForeignKey("buyers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("reservation_date", sa.String(30), nullable=False),
        sa.Column("expiry_date", sa.String(30), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("notes", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_reservations_unit_id", "reservations", ["unit_id"])
    op.create_index("ix_reservations_buyer_id", "reservations", ["buyer_id"])

    op.create_table(
        "sales_contracts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "unit_id",
            sa.String(36),
            sa.ForeignKey("units.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "buyer_id",
            sa.String(36),
            sa.ForeignKey("buyers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "reservation_id",
            sa.String(36),
            sa.ForeignKey("reservations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("contract_number", sa.String(100), nullable=False, unique=True),
        sa.Column("contract_date", sa.String(30), nullable=False),
        sa.Column("contract_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("notes", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sales_contracts_unit_id", "sales_contracts", ["unit_id"])
    op.create_index("ix_sales_contracts_buyer_id", "sales_contracts", ["buyer_id"])
    op.create_index("ix_sales_contracts_reservation_id", "sales_contracts", ["reservation_id"])


def downgrade() -> None:
    op.drop_index("ix_sales_contracts_reservation_id", table_name="sales_contracts")
    op.drop_index("ix_sales_contracts_buyer_id", table_name="sales_contracts")
    op.drop_index("ix_sales_contracts_unit_id", table_name="sales_contracts")
    op.drop_table("sales_contracts")

    op.drop_index("ix_reservations_buyer_id", table_name="reservations")
    op.drop_index("ix_reservations_unit_id", table_name="reservations")
    op.drop_table("reservations")

    op.drop_index("ix_buyers_email", table_name="buyers")
    op.drop_table("buyers")
