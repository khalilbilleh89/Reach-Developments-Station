"""Company records and repeatable bank accounts; all entry fields nullable.

Revision ID: 0033_project_company
Revises: 0032_building_units
"""

import sqlalchemy as sa
from alembic import op

revision = "0033_project_company"
down_revision = "0032_building_units"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_companies",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("legal_name", sa.String(320), nullable=True),
        sa.Column("trading_name", sa.String(320), nullable=True),
        sa.Column("registration_number", sa.String(320), nullable=True),
        sa.Column("tax_number", sa.String(320), nullable=True),
        sa.Column("legal_form", sa.String(320), nullable=True),
        sa.Column("country", sa.String(320), nullable=True),
        sa.Column("registered_address", sa.String(2000), nullable=True),
        sa.Column("contact_name", sa.String(320), nullable=True),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("phone", sa.String(320), nullable=True),
        sa.Column("website", sa.String(320), nullable=True),
        sa.Column("authorized_signatory", sa.String(320), nullable=True),
        sa.Column("notes", sa.String(2000), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_project_companies"),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_project_companies_project_id_projects",
            ondelete="RESTRICT",
        ),
    )
    op.create_index("ix_project_companies_project_id", "project_companies", ["project_id"])
    op.create_table(
        "company_bank_accounts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("beneficiary_name", sa.String(320), nullable=True),
        sa.Column("beneficiary_bank", sa.String(320), nullable=True),
        sa.Column("account_number", sa.String(320), nullable=True),
        sa.Column("iban", sa.String(320), nullable=True),
        sa.Column("swift_code", sa.String(320), nullable=True),
        sa.Column("bank_address", sa.String(2000), nullable=True),
        sa.Column("correspondent_bank", sa.String(320), nullable=True),
        sa.Column("correspondent_swift_code", sa.String(320), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_company_bank_accounts"),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["project_companies.id"],
            name="fk_company_bank_accounts_company_id_project_companies",
            ondelete="RESTRICT",
        ),
    )
    op.create_index("ix_company_bank_accounts_company_id", "company_bank_accounts", ["company_id"])


def downgrade() -> None:
    connection = op.get_bind()
    for table in ("company_bank_accounts", "project_companies"):
        if connection.execute(sa.text(f"SELECT EXISTS (SELECT 1 FROM {table})")).scalar():
            raise RuntimeError("Company history exists; retain this migration and roll forward.")
    op.drop_table("company_bank_accounts")
    op.drop_table("project_companies")
