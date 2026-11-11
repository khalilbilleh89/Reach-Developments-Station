"""Optional company profiles, bank instructions, document links and retained logos."""

import sqlalchemy as sa
from alembic import op

revision = "0069_company_profile"
down_revision = "0068_site_reports"
branch_labels = None
depends_on = None

COMPANY = {
    "project_role": sa.String(32),
    "other_role": sa.String(320),
    "relationship": sa.String(32),
    "related_company_id": sa.UUID(),
    "ownership_percentage": sa.Numeric(7, 4),
    "incorporation_date": sa.Date(),
    "status": sa.String(32),
}
BANK = {
    "account_purpose": sa.String(32),
    "currency_code": sa.String(3),
    "default_for_payments": sa.Boolean(),
    "last_verified_date": sa.Date(),
    "status": sa.String(32),
    "bank_country": sa.String(320),
}
DOCUMENT = {
    "source_url": sa.String(2000),
    "category": sa.String(320),
    "linked_record": sa.String(500),
    "issue_date": sa.Date(),
    "expiry_date": sa.Date(),
    "reminder_date": sa.Date(),
    "verification_status": sa.String(32),
}
TABLES = {
    "project_companies": COMPANY,
    "company_bank_accounts": BANK,
    "company_documents": DOCUMENT,
}


def upgrade() -> None:
    for table, columns in TABLES.items():
        for name, kind in columns.items():
            op.add_column(table, sa.Column(name, kind, nullable=True))
    op.create_foreign_key(
        "fk_project_companies_related_company_id_project_companies",
        "project_companies",
        "project_companies",
        ["related_company_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    for name in ("filename", "document", "sha256"):
        op.alter_column("company_documents", name, nullable=True)
    op.create_check_constraint(
        op.f("ck_company_documents_one_source"),
        "company_documents",
        "(document IS NOT NULL AND filename IS NOT NULL AND sha256 IS NOT NULL "
        "AND source_url IS NULL) OR (document IS NULL AND filename IS NULL "
        "AND sha256 IS NULL AND source_url IS NOT NULL)",
    )
    op.create_table(
        "company_logos",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "company_id",
            sa.UUID(),
            sa.ForeignKey("project_companies.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("image", sa.LargeBinary(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_company_logos_company_id", "company_logos", ["company_id"])
    op.create_index(
        "uq_company_logos_active",
        "company_logos",
        ["company_id"],
        unique=True,
        postgresql_where=sa.text("NOT is_deleted"),
    )
    op.create_index(
        "uq_company_bank_default",
        "company_bank_accounts",
        ["company_id"],
        unique=True,
        postgresql_where=sa.text("NOT is_deleted AND default_for_payments"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM company_logos)")):
        raise RuntimeError("Company logos exist; retain this migration and roll forward.")
    for table, columns in TABLES.items():
        predicate = " OR ".join(f"{name} IS NOT NULL" for name in columns)
        if bind.scalar(sa.text(f"SELECT EXISTS (SELECT 1 FROM {table} WHERE {predicate})")):
            raise RuntimeError(
                "Company profile data exists; retain this migration and roll forward."
            )
    op.drop_index("uq_company_bank_default", table_name="company_bank_accounts")
    op.drop_table("company_logos")
    op.drop_constraint(op.f("ck_company_documents_one_source"), "company_documents", type_="check")
    for name in ("filename", "document", "sha256"):
        op.alter_column("company_documents", name, nullable=False)
    op.drop_constraint(
        "fk_project_companies_related_company_id_project_companies",
        "project_companies",
        type_="foreignkey",
    )
    for table, columns in TABLES.items():
        for name in columns:
            op.drop_column(table, name)
