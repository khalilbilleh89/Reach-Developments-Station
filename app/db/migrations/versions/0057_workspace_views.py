"""Per-person saved register views and register preferences.

Revision ID: 0057_workspace_views
Revises: 0056_project_drawings
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0057_workspace_views"
down_revision = "0056_project_drawings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_saved_views",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("screen", sa.String(80), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column(
            "filters",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("sort", sa.String(80), nullable=True),
        sa.Column("pinned", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id", name="pk_user_saved_views"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_user_saved_views_user_id_users", ondelete="RESTRICT"
        ),
        sa.UniqueConstraint(
            "user_id", "screen", "name", name="uq_user_saved_views_user_screen_name"
        ),
        sa.CheckConstraint("length(trim(screen)) > 0", name="ck_user_saved_views_screen_present"),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_user_saved_views_name_present"),
    )
    op.create_index("ix_user_saved_views_user_id_screen", "user_saved_views", ["user_id", "screen"])
    op.create_table(
        "user_preferences",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "register_density",
            sa.String(16),
            nullable=False,
            server_default=sa.text("'comfortable'"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("user_id", name="pk_user_preferences"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_user_preferences_user_id_users", ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "register_density IN ('comfortable','compact')",
            name="ck_user_preferences_valid_register_density",
        ),
    )


def downgrade() -> None:
    # Working habits, not evidence: a downgrade may discard them.
    op.drop_table("user_preferences")
    op.drop_index("ix_user_saved_views_user_id_screen", table_name="user_saved_views")
    op.drop_table("user_saved_views")
