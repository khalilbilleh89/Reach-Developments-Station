"""Project Agent roster and optional identity links; no name-based backfill.

Existing free-text attribution stays untouched. Downgrade refuses to discard a
registered Agent; export or remove unused records through the governed workflow.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0036_sales_agents"
down_revision = "0035_merge_company_current_costs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sales_agents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("country", sa.String(200)),
        sa.Column("branch", sa.String(200)),
        sa.Column("branch_leader", sa.String(200)),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "created_by_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "updated_by_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT")
        ),
        sa.UniqueConstraint("id", "project_id", name="sales_agent_project"),
        sa.CheckConstraint("length(trim(display_name)) > 0", name="ck_sales_agents_name_not_blank"),
    )
    op.create_index("ix_sales_agents_project_active", "sales_agents", ["project_id", "is_active"])
    for table in ("clients", "reservations", "sale_contracts"):
        op.add_column(table, sa.Column("agent_id", UUID(as_uuid=True), nullable=True))
        op.create_foreign_key(
            "agent",
            table,
            "sales_agents",
            ["agent_id", "project_id"],
            ["id", "project_id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM sales_agents")):
        raise RuntimeError("Registered Agents must be removed or exported before rollback.")
    for table in ("sale_contracts", "reservations", "clients"):
        op.drop_constraint("agent", table, type_="foreignkey")
        op.drop_column(table, "agent_id")
    op.drop_index("ix_sales_agents_project_active", table_name="sales_agents")
    op.drop_table("sales_agents")
