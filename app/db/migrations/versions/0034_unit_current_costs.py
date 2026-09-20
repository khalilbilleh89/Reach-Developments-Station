"""Current unit cost analysis inputs; historical allocations remain unchanged."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0034_unit_current_costs"
down_revision = "0033_contract_payments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ue_current_cost_settings",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("currency_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("gross_area_type_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("supplemental_soft_cost", sa.Numeric(18, 2)),
        sa.Column("additional_cost", sa.Numeric(18, 2)),
        sa.Column("finance_cost", sa.Numeric(18, 2)),
        sa.Column("commission_rate_fraction", sa.Numeric(9, 6)),
        sa.Column("profit_tax_rate_fraction", sa.Numeric(9, 6)),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("notes", sa.String(1000)),
        sa.PrimaryKeyConstraint("project_id"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["currency_id"], ["currencies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["gross_area_type_id", "project_id"],
            ["area_types.id", "area_types.project_id"],
            name="fk_ue_current_gross_area",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("revision > 0", name="revision_positive"),
        *(
            sa.CheckConstraint(f"{field} IS NULL OR {field} >= 0", name=f"{field}_nonnegative")
            for field in ("supplemental_soft_cost", "additional_cost", "finance_cost")
        ),
        *(
            sa.CheckConstraint(f"{field} IS NULL OR {field} BETWEEN 0 AND 1", name=f"{field}_range")
            for field in ("commission_rate_fraction", "profit_tax_rate_fraction")
        ),
    )


def downgrade() -> None:
    if op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT 1 FROM ue_current_cost_settings)")):
        raise RuntimeError("Current cost settings must be removed with audit before downgrade.")
    op.drop_table("ue_current_cost_settings")
