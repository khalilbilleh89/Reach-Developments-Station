"""Store project presentation images with retained removal history.

Revision ID: 0039_project_images
Revises: 0038_commission_beneficiaries
"""

import sqlalchemy as sa
from alembic import op

revision = "0039_project_images"
down_revision = "0038_commission_beneficiaries"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_images",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("category", sa.String(24), nullable=False),
        sa.Column("filename", sa.String(200), nullable=False),
        sa.Column("media_type", sa.String(32), nullable=False),
        sa.Column("image_data", sa.LargeBinary(), nullable=False),
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("removed_by_user_id", sa.UUID(), nullable=True),
        sa.CheckConstraint(
            "category IN ('interior', 'exterior', 'render_3d')",
            name="ck_project_images_category_allowed",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_project_images_project_id_projects",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_project_images_created_by_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["removed_by_user_id"],
            ["users.id"],
            name="fk_project_images_removed_by_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_project_images"),
    )
    op.create_index("ix_project_images_project_id", "project_images", ["project_id"])


def downgrade() -> None:
    if op.get_bind().execute(sa.text("SELECT EXISTS (SELECT 1 FROM project_images)")).scalar():
        raise RuntimeError("Project image history exists; retain this migration and roll forward.")
    op.drop_index("ix_project_images_project_id", table_name="project_images")
    op.drop_table("project_images")
