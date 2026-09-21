"""Classify existing allocations as legacy and add structured beneficiary identity.

No names are matched to Agent IDs or Sale branches; financial values are untouched.
"""

import sqlalchemy as sa
from alembic import op

revision = "0038_commission_beneficiaries"
down_revision = "0037_merge_sales"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "commission_allocations", sa.Column("beneficiary_type", sa.String(16), nullable=True)
    )
    op.add_column("commission_allocations", sa.Column("sales_agent_id", sa.UUID(), nullable=True))
    op.add_column(
        "commission_allocations",
        sa.Column("beneficiary_branch_snapshot", sa.String(200), nullable=True),
    )
    op.execute("UPDATE commission_allocations SET beneficiary_type = 'legacy'")
    op.alter_column("commission_allocations", "beneficiary_type", nullable=False)
    op.alter_column("commission_allocations", "beneficiary_name", nullable=True)
    op.drop_constraint(
        op.f("ck_commission_allocations_beneficiary_present"),
        "commission_allocations",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_commission_allocations_beneficiary_present"),
        "commission_allocations",
        "beneficiary_name IS NULL OR length(trim(beneficiary_name)) > 0",
    )
    op.create_check_constraint(
        op.f("ck_commission_allocations_beneficiary_type_ok"),
        "commission_allocations",
        "beneficiary_type IN ('agent', 'branch', 'other', 'legacy')",
    )
    op.create_check_constraint(
        op.f("ck_commission_allocations_beneficiary_shape"),
        "commission_allocations",
        "(beneficiary_type = 'agent' AND sales_agent_id IS NOT NULL "
        "AND beneficiary_name IS NOT NULL) OR "
        "(beneficiary_type IN ('branch', 'legacy') AND sales_agent_id IS NULL "
        "AND beneficiary_name IS NOT NULL AND beneficiary_branch_snapshot IS NULL) OR "
        "(beneficiary_type = 'other' AND sales_agent_id IS NULL "
        "AND beneficiary_branch_snapshot IS NULL)",
    )
    op.create_foreign_key(
        op.f("fk_commission_allocations_commission_agent_sales_agents"),
        "commission_allocations",
        "sales_agents",
        ["sales_agent_id", "project_id"],
        ["id", "project_id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    if op.get_bind().scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM commission_allocations "
            "WHERE beneficiary_type <> 'legacy' OR beneficiary_name IS NULL)"
        )
    ):
        raise RuntimeError("Structured commission beneficiaries must be retained before rollback.")
    op.drop_constraint(
        op.f("fk_commission_allocations_commission_agent_sales_agents"),
        "commission_allocations",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("ck_commission_allocations_beneficiary_shape"),
        "commission_allocations",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_commission_allocations_beneficiary_type_ok"),
        "commission_allocations",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_commission_allocations_beneficiary_present"),
        "commission_allocations",
        type_="check",
    )
    op.alter_column("commission_allocations", "beneficiary_name", nullable=False)
    op.create_check_constraint(
        op.f("ck_commission_allocations_beneficiary_present"),
        "commission_allocations",
        "length(trim(beneficiary_name)) > 0",
    )
    op.drop_column("commission_allocations", "beneficiary_branch_snapshot")
    op.drop_column("commission_allocations", "sales_agent_id")
    op.drop_column("commission_allocations", "beneficiary_type")
