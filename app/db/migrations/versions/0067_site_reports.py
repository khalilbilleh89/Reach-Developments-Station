"""Site report PDFs with metadata and retained removal.

Revision ID: 0067_site_reports
Revises: 0066_client_links
"""

import sqlalchemy as sa
from alembic import op

revision = "0067_site_reports"
down_revision = "0066_client_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_site_reports",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(320), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("notes", sa.String(2000), nullable=False),
        sa.Column("filename", sa.String(255), nullable=True),
        sa.Column("document", sa.LargeBinary(), nullable=True),
        sa.Column("sha256", sa.String(64), nullable=True),
        sa.Column("source_url", sa.String(2000), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id", name="pk_project_site_reports"),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_project_site_reports_project_id_projects",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "length(trim(title)) > 0", name=op.f("ck_project_site_reports_title_present")
        ),
        sa.CheckConstraint(
            "octet_length(document) BETWEEN 1 AND 52428800",
            name=op.f("ck_project_site_reports_document_size"),
        ),
        sa.CheckConstraint(
            "(source_url IS NULL AND document IS NOT NULL AND filename IS NOT NULL "
            "AND sha256 IS NOT NULL) OR (source_url IS NOT NULL AND length(trim(source_url)) > 0 "
            "AND document IS NULL AND filename IS NULL AND sha256 IS NULL)",
            name=op.f("ck_project_site_reports_one_source"),
        ),
        sa.CheckConstraint("version > 0", name=op.f("ck_project_site_reports_positive_version")),
    )
    op.create_index("ix_project_site_reports_project_id", "project_site_reports", ["project_id"])


def downgrade() -> None:
    if (
        op.get_bind()
        .execute(sa.text("SELECT EXISTS (SELECT 1 FROM project_site_reports)"))
        .scalar()
    ):
        raise RuntimeError("Site reports exist; retain this migration and roll forward.")
    op.drop_table("project_site_reports")
