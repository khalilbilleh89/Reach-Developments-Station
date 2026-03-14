"""create sales exceptions table

Revision ID: 0010
Revises: 0009
Create Date: 2026-03-14

Creates the sales exceptions / incentives persistence layer:
  sales_exceptions

FK relationships
----------------
  sales_exceptions.project_id        → projects.id        (CASCADE)
  sales_exceptions.unit_id           → units.id           (CASCADE)
  sales_exceptions.sale_contract_id  → sales_contracts.id (SET NULL)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sales_exceptions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "unit_id",
            sa.String(36),
            sa.ForeignKey("units.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "sale_contract_id",
            sa.String(36),
            sa.ForeignKey("sales_contracts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("exception_type", sa.String(50), nullable=False),
        sa.Column("base_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("requested_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("discount_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("discount_percentage", sa.Numeric(8, 4), nullable=False),
        sa.Column("incentive_value", sa.Numeric(14, 2), nullable=True),
        sa.Column("incentive_description", sa.String(500), nullable=True),
        sa.Column(
            "approval_status",
            sa.String(50),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("requested_by", sa.String(200), nullable=True),
        sa.Column("approved_by", sa.String(200), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.String(2000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sales_exceptions_project_id", "sales_exceptions", ["project_id"])
    op.create_index("ix_sales_exceptions_unit_id", "sales_exceptions", ["unit_id"])
    op.create_index(
        "ix_sales_exceptions_sale_contract_id",
        "sales_exceptions",
        ["sale_contract_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_sales_exceptions_sale_contract_id", table_name="sales_exceptions")
    op.drop_index("ix_sales_exceptions_unit_id", table_name="sales_exceptions")
    op.drop_index("ix_sales_exceptions_project_id", table_name="sales_exceptions")
    op.drop_table("sales_exceptions")
