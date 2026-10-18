"""Add project price escalation strategy register."""

import sqlalchemy as sa
from alembic import op

revision = "0049_price_escalation"
down_revision = "0045_inventory_masterplans"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_price_escalations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("escalation_rate_fraction", sa.Numeric(9, 6), nullable=False),
        sa.Column("project_status", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "escalation_rate_fraction > 0 AND escalation_rate_fraction < 1000",
            name=op.f("ck_project_price_escalations_rate"),
        ),
        sa.CheckConstraint(
            "length(trim(project_status)) BETWEEN 1 AND 200",
            name=op.f("ck_project_price_escalations_status"),
        ),
        sa.CheckConstraint("version > 0", name=op.f("ck_project_price_escalations_version")),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_project_price_escalations_project_id_projects",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_project_price_escalations"),
    )
    op.create_index(
        "ix_project_price_escalations_project_id", "project_price_escalations", ["project_id"]
    )


def downgrade() -> None:
    if (
        op.get_bind()
        .execute(sa.text("SELECT EXISTS (SELECT 1 FROM project_price_escalations)"))
        .scalar()
    ):
        raise RuntimeError(
            "Price escalation history exists; retain this migration and roll forward."
        )
    op.drop_table("project_price_escalations")
