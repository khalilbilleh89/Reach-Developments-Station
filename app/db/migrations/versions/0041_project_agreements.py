"""Project final agreement drafts and retained documents.

Revision ID: 0041_project_agreements
Revises: 0040_project_team
"""

import sqlalchemy as sa
from alembic import op

revision = "0041_project_agreements"
down_revision = "0040_project_team"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_agreements",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(320), nullable=False),
        sa.Column("signing_company", sa.String(320), nullable=False),
        sa.Column("draft_created_on", sa.Date(), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("document", sa.LargeBinary(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id", name="pk_project_agreements"),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_project_agreements_project_id_projects",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "length(trim(name)) > 0", name=op.f("ck_project_agreements_name_present")
        ),
        sa.CheckConstraint(
            "length(trim(signing_company)) > 0", name=op.f("ck_project_agreements_company_present")
        ),
        sa.CheckConstraint(
            "octet_length(document) BETWEEN 1 AND 10485760",
            name=op.f("ck_project_agreements_document_size"),
        ),
        sa.CheckConstraint("version > 0", name=op.f("ck_project_agreements_positive_version")),
    )
    op.create_index("ix_project_agreements_project_id", "project_agreements", ["project_id"])


def downgrade() -> None:
    if op.get_bind().execute(sa.text("SELECT EXISTS (SELECT 1 FROM project_agreements)")).scalar():
        raise RuntimeError("Agreement documents exist; retain this migration and roll forward.")
    op.drop_table("project_agreements")
