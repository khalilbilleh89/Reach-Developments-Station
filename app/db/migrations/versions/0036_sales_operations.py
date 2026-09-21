"""Project buyer operations; original commercial records are untouched."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0036_sales_operations"
down_revision = "0035_merge_company_current_costs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "operation_pipelines",
        sa.Column("project_id", postgresql.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("project_id"),
    )
    op.create_table(
        "operation_stages",
        sa.Column("id", postgresql.UUID(), nullable=False),
        sa.Column("project_id", postgresql.UUID(), nullable=False),
        sa.Column("label", sa.String(160), nullable=False),
        sa.Column("section", sa.String(24), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(24), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["operation_pipelines.project_id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "project_id", name="uq_operation_stage_project"),
        sa.CheckConstraint("length(trim(label)) > 0", name="label_nonempty"),
        sa.CheckConstraint("section IN ('property_purchase', 'golden_visa')", name="section_ok"),
        sa.CheckConstraint("source IN ('manual', 'buyer_signed_spa')", name="source_ok"),
        sa.CheckConstraint("position >= 0", name="position_nonnegative"),
    )
    op.create_table(
        "operation_buyers",
        sa.Column("client_id", postgresql.UUID(), nullable=False),
        sa.Column("project_id", postgresql.UUID(), nullable=False),
        sa.Column("purpose", sa.String(24), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("client_id"),
        sa.ForeignKeyConstraint(
            ["client_id", "project_id"],
            ["clients.id", "clients.project_id"],
            ondelete="RESTRICT",
            name="fk_operation_buyer_client",
        ),
        sa.UniqueConstraint("client_id", "project_id", name="uq_operation_buyer_project"),
        sa.CheckConstraint(
            "purpose IS NULL OR purpose IN ('investment_only', 'golden_visa')", name="purpose_ok"
        ),
    )
    op.create_table(
        "operation_progress",
        sa.Column("client_id", postgresql.UUID(), nullable=False),
        sa.Column("stage_id", postgresql.UUID(), nullable=False),
        sa.Column("project_id", postgresql.UUID(), nullable=False),
        sa.Column("completed", sa.Boolean(), nullable=True),
        sa.Column("completed_date", sa.Date(), nullable=True),
        sa.PrimaryKeyConstraint("client_id", "stage_id"),
        sa.ForeignKeyConstraint(
            ["client_id", "project_id"],
            ["operation_buyers.client_id", "operation_buyers.project_id"],
            ondelete="RESTRICT",
            name="fk_operation_progress_buyer",
        ),
        sa.ForeignKeyConstraint(
            ["stage_id", "project_id"],
            ["operation_stages.id", "operation_stages.project_id"],
            ondelete="RESTRICT",
            name="fk_operation_progress_stage",
        ),
        sa.CheckConstraint("completed IS TRUE OR completed_date IS NULL", name="date_requires_yes"),
    )


def downgrade() -> None:
    if op.get_bind().scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM operation_buyers) "
            "OR EXISTS (SELECT 1 FROM operation_pipelines)"
        )
    ):
        raise RuntimeError(
            "Operations contains retained configuration or buyer history. "
            "Export and roll forward; do not drop recorded evidence."
        )
    for table in (
        "operation_progress",
        "operation_buyers",
        "operation_stages",
        "operation_pipelines",
    ):
        op.drop_table(table)
