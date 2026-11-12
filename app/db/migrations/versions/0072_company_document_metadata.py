"""Record company relationship choices and registration document metadata."""

import sqlalchemy as sa
from alembic import op

revision = "0072_company_document_metadata"
down_revision = "0071_report_sections"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "project_companies",
        sa.Column("no_related_company", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_check_constraint(
        "related_company_choice",
        "project_companies",
        "NOT no_related_company OR related_company_id IS NULL",
    )
    op.add_column("company_documents", sa.Column("other_category", sa.String(320)))
    op.add_column(
        "company_documents",
        sa.Column("issue_date_not_stated", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("company_documents", sa.Column("expiry_note", sa.String(32)))
    op.add_column("company_documents", sa.Column("reminder_days", sa.Integer()))
    op.execute(
        """
        UPDATE company_documents
        SET category = 'Registered office/address certificate',
            issue_date = COALESCE(issue_date, DATE '2024-07-04'),
            expiry_note = CASE WHEN expiry_date IS NULL THEN 'not_stated' END,
            verification_status = COALESCE(verification_status, 'needs_review'),
            version = version + 1
        WHERE NOT is_deleted
          AND (
            lower(regexp_replace(label, '[^a-zA-Z0-9]', '', 'g'))
                IN ('aqaratdevelopmentaddresscertificate', 'aqaratdevelopmentaddresscertificatepdf')
            OR lower(regexp_replace(filename, '[^a-zA-Z0-9]', '', 'g'))
                = 'aqaratdevelopmentaddresscertificatepdf'
          )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE company_documents
        SET category = CASE WHEN category = 'Other' THEN COALESCE(other_category, category)
                            ELSE category END,
            verification_status = CASE WHEN verification_status IN ('expired', 'superseded')
                                       THEN 'needs_review' ELSE verification_status END
        WHERE other_category IS NOT NULL OR verification_status IN ('expired', 'superseded')
        """
    )
    op.drop_column("company_documents", "reminder_days")
    op.drop_column("company_documents", "expiry_note")
    op.drop_column("company_documents", "issue_date_not_stated")
    op.drop_column("company_documents", "other_category")
    op.drop_constraint(
        op.f("ck_project_companies_related_company_choice"), "project_companies", type_="check"
    )
    op.drop_column("project_companies", "no_related_company")
