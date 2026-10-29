"""Project drawing PDFs with metadata and retained removal.

Revision ID: 0053_project_drawings
Revises: 0052_design_payments
"""

import sqlalchemy as sa
from alembic import op

revision = "0053_project_drawings"
down_revision = "0052_design_payments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_drawings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(320), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("drawing_number", sa.String(120), nullable=False),
        sa.Column("location", sa.String(200), nullable=False),
        sa.Column("revision", sa.String(80), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("notes", sa.String(2000), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("document", sa.LargeBinary(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id", name="pk_project_drawings"),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_project_drawings_project_id_projects",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("length(trim(name)) > 0", name=op.f("ck_project_drawings_name_present")),
        sa.CheckConstraint(
            "octet_length(document) BETWEEN 1 AND 10485760",
            name=op.f("ck_project_drawings_document_size"),
        ),
        sa.CheckConstraint(
            "category IN ('general','architecture','structure','mep','landscape','interiors')",
            name=op.f("ck_project_drawings_valid_category"),
        ),
        sa.CheckConstraint(
            "status IN ('reference','for_review','issued','superseded')",
            name=op.f("ck_project_drawings_valid_status"),
        ),
        sa.CheckConstraint("version > 0", name=op.f("ck_project_drawings_positive_version")),
    )
    op.create_index("ix_project_drawings_project_id", "project_drawings", ["project_id"])


def downgrade() -> None:
    if op.get_bind().execute(sa.text("SELECT EXISTS (SELECT 1 FROM project_drawings)")).scalar():
        raise RuntimeError("Project drawings exist; retain this migration and roll forward.")
    op.drop_table("project_drawings")
