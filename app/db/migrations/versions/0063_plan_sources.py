"""50 MB plan PDFs and retained Google Drive link sources."""

import sqlalchemy as sa
from alembic import op

revision = "0063_plan_sources"
down_revision = "0062_project_training"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("project_drawings", sa.Column("source_url", sa.String(2000)))
    for name, kind in [
        ("filename", sa.String(255)),
        ("sha256", sa.String(64)),
        ("document", sa.LargeBinary()),
    ]:
        op.alter_column("project_drawings", name, existing_type=kind, nullable=True)
    op.drop_constraint(op.f("ck_project_drawings_document_size"), "project_drawings", type_="check")
    op.create_check_constraint(
        op.f("ck_project_drawings_document_size"),
        "project_drawings",
        "octet_length(document) BETWEEN 1 AND 52428800",
    )
    op.create_check_constraint(
        op.f("ck_project_drawings_one_source"),
        "project_drawings",
        "(source_url IS NULL AND document IS NOT NULL AND filename IS NOT NULL "
        "AND sha256 IS NOT NULL) OR (source_url IS NOT NULL AND length(trim(source_url)) > 0 "
        "AND document IS NULL AND filename IS NULL AND sha256 IS NULL)",
    )


def downgrade() -> None:
    if (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT EXISTS (SELECT 1 FROM project_drawings WHERE source_url IS NOT NULL "
                "OR octet_length(document) > 10485760)"
            )
        )
        .scalar()
    ):
        raise RuntimeError(
            "Large PDFs or Drive links exist; retain this migration and roll forward."
        )
    op.drop_constraint(op.f("ck_project_drawings_one_source"), "project_drawings", type_="check")
    op.drop_constraint(op.f("ck_project_drawings_document_size"), "project_drawings", type_="check")
    op.create_check_constraint(
        op.f("ck_project_drawings_document_size"),
        "project_drawings",
        "octet_length(document) BETWEEN 1 AND 10485760",
    )
    for name, kind in [
        ("filename", sa.String(255)),
        ("sha256", sa.String(64)),
        ("document", sa.LargeBinary()),
    ]:
        op.alter_column("project_drawings", name, existing_type=kind, nullable=False)
    op.drop_column("project_drawings", "source_url")
