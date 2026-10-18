"""Company registration PDFs with labels and retained removal.

Revision ID: 0046_company_documents
Revises: 0045_inventory_masterplans
"""

import sqlalchemy as sa
from alembic import op

revision = "0046_company_documents"
down_revision = "0045_inventory_masterplans"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "company_documents",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("label", sa.String(320), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("document", sa.LargeBinary(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id", name="pk_company_documents"),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["project_companies.id"],
            name="fk_company_documents_company_id_project_companies",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "length(trim(label)) > 0", name=op.f("ck_company_documents_label_present")
        ),
        sa.CheckConstraint(
            "octet_length(document) BETWEEN 1 AND 10485760",
            name=op.f("ck_company_documents_document_size"),
        ),
        sa.CheckConstraint("version > 0", name=op.f("ck_company_documents_positive_version")),
    )
    op.create_index("ix_company_documents_company_id", "company_documents", ["company_id"])


def downgrade() -> None:
    if op.get_bind().execute(sa.text("SELECT EXISTS (SELECT 1 FROM company_documents)")).scalar():
        raise RuntimeError("Company documents exist; retain this migration and roll forward.")
    op.drop_table("company_documents")
