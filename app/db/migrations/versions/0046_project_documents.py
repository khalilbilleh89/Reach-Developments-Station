"""Project document types and retained PDF evidence."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0046_project_documents"
down_revision = "0045_inventory_masterplans"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_document_types",
        sa.Column("id", postgresql.UUID(), nullable=False),
        sa.Column("project_id", postgresql.UUID(), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("project_id", "code"),
        sa.CheckConstraint(
            "length(trim(label)) > 0", name=op.f("ck_project_document_types_label_not_blank")
        ),
    )
    op.create_index(
        "ix_project_document_types_project_id", "project_document_types", ["project_id"]
    )
    op.alter_column(
        "document_references", "external_url", existing_type=sa.String(2000), nullable=True
    )
    op.add_column("document_references", sa.Column("filename", sa.String(255), nullable=True))
    op.add_column("document_references", sa.Column("document", sa.LargeBinary(), nullable=True))
    op.add_column("document_references", sa.Column("sha256", sa.String(64), nullable=True))
    op.add_column(
        "document_references",
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )

    op.create_check_constraint(
        op.f("ck_document_references_source_valid"),
        "document_references",
        "(external_url IS NOT NULL AND filename IS NULL AND document IS NULL "
        "AND sha256 IS NULL) OR (external_url IS NULL AND filename IS NOT NULL "
        "AND document IS NOT NULL AND sha256 IS NOT NULL "
        "AND octet_length(document) BETWEEN 1 AND 10485760)",
    )


def downgrade() -> None:
    if op.get_bind().scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM project_document_types) "
            "OR EXISTS (SELECT 1 FROM document_references "
            "WHERE filename IS NOT NULL OR is_deleted)"
        )
    ):
        raise RuntimeError("Retained document history prevents downgrade; roll forward.")
    op.drop_constraint(
        op.f("ck_document_references_source_valid"), "document_references", type_="check"
    )
    for column in ("is_deleted", "sha256", "document", "filename"):
        op.drop_column("document_references", column)
    op.alter_column(
        "document_references", "external_url", existing_type=sa.String(2000), nullable=False
    )
    op.drop_table("project_document_types")
