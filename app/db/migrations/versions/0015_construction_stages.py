"""Project construction stages and append-only unit completion history."""

import sqlalchemy as sa
from alembic import op

revision = "0015_construction_stages"
down_revision = "0014_direct_unit_price"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "construction_stages",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("project_id", sa.UUID(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("planned_date", sa.Date(), nullable=True),
        sa.UniqueConstraint("project_id", "name"),
        sa.UniqueConstraint("project_id", "sequence"),
        sa.UniqueConstraint("id", "project_id"),
        sa.CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
        sa.CheckConstraint("sequence > 0", name="sequence_positive"),
    )
    op.create_table(
        "unit_stage_events",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("unit_id", sa.UUID(), nullable=False),
        sa.Column("stage_id", sa.UUID(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("completed_date", sa.Date(), nullable=True),
        sa.Column("reason", sa.String(1000), nullable=False),
        sa.Column("actor_user_id", sa.UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "recorded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["unit_id", "project_id"], ["units.id", "units.project_id"]),
        sa.ForeignKeyConstraint(
            ["stage_id", "project_id"], ["construction_stages.id", "construction_stages.project_id"]
        ),
        sa.UniqueConstraint("unit_id", "stage_id", "sequence"),
        sa.CheckConstraint("sequence > 0", name="sequence_positive"),
        sa.CheckConstraint("length(trim(reason)) > 0", name="reason_not_blank"),
    )


def downgrade() -> None:
    if op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT 1 FROM construction_stages)")):
        raise RuntimeError("Construction stages exist. Retain the schema or restore a backup.")
    op.drop_table("unit_stage_events")
    op.drop_table("construction_stages")
