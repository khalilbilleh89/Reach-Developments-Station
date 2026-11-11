"""Separate fixed client-linked operations commissions; preserve sales history."""

import sqlalchemy as sa
from alembic import op

revision = "0070_operations_commissions"
down_revision = "0069_company_profile"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "operations_commissions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("client_id", sa.UUID(), nullable=False),
        sa.Column("client_display", sa.String(300), nullable=False),
        sa.Column("beneficiary_name", sa.String(200), nullable=False),
        sa.Column("reason", sa.String(2000), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_operations_commissions"),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            ondelete="RESTRICT",
            name="fk_operations_commissions_project_id_projects",
        ),
        sa.ForeignKeyConstraint(
            ["currency_id"],
            ["currencies.id"],
            ondelete="RESTRICT",
            name="fk_operations_commissions_currency_id_currencies",
        ),
        sa.ForeignKeyConstraint(
            ["client_id", "project_id"],
            ["clients.id", "clients.project_id"],
            ondelete="RESTRICT",
            name="fk_ops_commission_client",
        ),
        sa.CheckConstraint("amount > 0 AND amount < 'Infinity'::numeric", name="amount_positive"),
        sa.CheckConstraint("length(trim(beneficiary_name)) > 0", name="beneficiary_present"),
        sa.CheckConstraint("length(trim(reason)) > 0", name="reason_present"),
        sa.CheckConstraint("version > 0", name="version_positive"),
    )
    op.create_index(
        "ix_operations_commissions_project_id", "operations_commissions", ["project_id"]
    )


def downgrade() -> None:
    if op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT 1 FROM operations_commissions)")):
        raise RuntimeError(
            "Cannot remove retained operations commission evidence; keep this migration."
        )
    op.drop_index("ix_operations_commissions_project_id", table_name="operations_commissions")
    op.drop_table("operations_commissions")
