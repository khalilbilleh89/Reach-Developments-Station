"""create registration tables

Revision ID: 0009
Revises: 0008
Create Date: 2026-03-14

Creates the registration/conveyancing persistence layer:
  registration_cases
  registration_milestones
  registration_documents

FK relationships
----------------
  registration_cases.project_id       → projects.id        (CASCADE)
  registration_cases.unit_id          → units.id           (CASCADE)
  registration_cases.sale_contract_id → sales_contracts.id (CASCADE)
  registration_milestones.registration_case_id → registration_cases.id (CASCADE)
  registration_documents.registration_case_id  → registration_cases.id (CASCADE)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # registration_cases
    # ------------------------------------------------------------------
    op.create_table(
        "registration_cases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "unit_id",
            sa.String(36),
            sa.ForeignKey("units.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "sale_contract_id",
            sa.String(36),
            sa.ForeignKey("sales_contracts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("buyer_name", sa.String(200), nullable=False),
        sa.Column("buyer_identifier", sa.String(100), nullable=True),
        sa.Column("jurisdiction", sa.String(100), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="draft"),
        sa.Column("opened_at", sa.Date, nullable=True),
        sa.Column("submitted_at", sa.Date, nullable=True),
        sa.Column("completed_at", sa.Date, nullable=True),
        sa.Column("notes", sa.String(2000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_registration_cases_project_id", "registration_cases", ["project_id"])
    op.create_index("ix_registration_cases_unit_id", "registration_cases", ["unit_id"])
    op.create_index(
        "ix_registration_cases_sale_contract_id",
        "registration_cases",
        ["sale_contract_id"],
    )

    # ------------------------------------------------------------------
    # registration_milestones
    # ------------------------------------------------------------------
    op.create_table(
        "registration_milestones",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "registration_case_id",
            sa.String(36),
            sa.ForeignKey("registration_cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("step_code", sa.String(50), nullable=False),
        sa.Column("step_name", sa.String(200), nullable=False),
        sa.Column("sequence", sa.Integer, nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("due_date", sa.Date, nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("remarks", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_registration_milestones_case_id",
        "registration_milestones",
        ["registration_case_id"],
    )

    # ------------------------------------------------------------------
    # registration_documents
    # ------------------------------------------------------------------
    op.create_table(
        "registration_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "registration_case_id",
            sa.String(36),
            sa.ForeignKey("registration_cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("document_type", sa.String(100), nullable=False),
        sa.Column(
            "is_required",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "is_received",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("received_at", sa.Date, nullable=True),
        sa.Column("reference_number", sa.String(100), nullable=True),
        sa.Column("remarks", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_registration_documents_case_id",
        "registration_documents",
        ["registration_case_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_registration_documents_case_id", table_name="registration_documents")
    op.drop_table("registration_documents")

    op.drop_index("ix_registration_milestones_case_id", table_name="registration_milestones")
    op.drop_table("registration_milestones")

    op.drop_index("ix_registration_cases_sale_contract_id", table_name="registration_cases")
    op.drop_index("ix_registration_cases_unit_id", table_name="registration_cases")
    op.drop_index("ix_registration_cases_project_id", table_name="registration_cases")
    op.drop_table("registration_cases")
