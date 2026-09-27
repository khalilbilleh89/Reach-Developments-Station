"""Project Team directory, independent of users and access grants."""

import sqlalchemy as sa
from alembic import op

revision = "0040_project_team"
down_revision = "0039_project_images"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_team_members",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("team", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("scope_of_work", sa.Text(), nullable=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "team IN ('operations', 'engineering')", name=op.f("ck_project_team_members_team")
        ),
        sa.CheckConstraint("length(trim(name)) > 0", name=op.f("ck_project_team_members_name")),
        sa.CheckConstraint("version > 0", name=op.f("ck_project_team_members_version")),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_project_team_members_project_id_projects",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_project_team_members"),
    )
    op.create_index("ix_project_team_members_project_id", "project_team_members", ["project_id"])


def downgrade() -> None:
    if (
        op.get_bind()
        .execute(sa.text("SELECT EXISTS (SELECT 1 FROM project_team_members)"))
        .scalar()
    ):
        raise RuntimeError("Team history exists; retain this migration and roll forward.")
    op.drop_table("project_team_members")
