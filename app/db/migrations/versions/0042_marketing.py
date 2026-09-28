"""Project marketing content and rental projections

Revision ID: 0042_marketing
Revises: 0041_project_agreements
Create Date: 2026-09-27 11:01:32.637274+00:00

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0042_marketing"
down_revision: str | Sequence[str] | None = "0041_project_agreements"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply this revision."""
    op.create_table(
        "marketing_content",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.CheckConstraint(
            "kind IN ('bio', 'branding')", name=op.f("ck_marketing_content_content_kind")
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_marketing_content_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_marketing_content")),
    )
    op.create_index(
        op.f("ix_marketing_content_project_id"), "marketing_content", ["project_id"], unique=False
    )
    op.create_index(
        "uq_marketing_content_live",
        "marketing_content",
        ["project_id", "kind"],
        unique=True,
        postgresql_where=sa.text("NOT is_deleted"),
    )
    op.create_table(
        "marketing_indicators",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=320), nullable=False),
        sa.Column("geography", sa.String(length=320), nullable=False),
        sa.Column("value", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("unit", sa.String(length=320), nullable=False),
        sa.Column("period", sa.String(length=320), nullable=False),
        sa.Column("source", sa.String(length=320), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("commentary", sa.String(length=4000), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_marketing_indicators_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_marketing_indicators")),
    )
    op.create_index(
        op.f("ix_marketing_indicators_project_id"),
        "marketing_indicators",
        ["project_id"],
        unique=False,
    )
    op.create_table(
        "marketing_rental_scenarios",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("unit_id", sa.UUID(), nullable=True),
        sa.Column("currency_id", sa.UUID(), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("area_basis", sa.String(length=20), nullable=False),
        sa.Column("exit_method", sa.String(length=20), nullable=False),
        sa.Column("price_override", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("annual_rent_per_sqm", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("annual_expense_per_sqm", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("setup_cost", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("vacancy_percent", sa.Numeric(precision=9, scale=4), nullable=False),
        sa.Column("discount_percent", sa.Numeric(precision=9, scale=4), nullable=False),
        sa.Column("acquisition_cost_percent", sa.Numeric(precision=9, scale=4), nullable=False),
        sa.Column("selling_cost_percent", sa.Numeric(precision=9, scale=4), nullable=False),
        sa.Column("income_growth_percent", sa.Numeric(precision=9, scale=4), nullable=False),
        sa.Column("expense_growth_percent", sa.Numeric(precision=9, scale=4), nullable=False),
        sa.Column("appreciation_percent", sa.Numeric(precision=9, scale=4), nullable=False),
        sa.Column("exit_cap_percent", sa.Numeric(precision=9, scale=4), nullable=False),
        sa.Column("source", sa.String(length=320), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.CheckConstraint(
            "area_basis IN ('net', 'gross')", name=op.f("ck_marketing_rental_scenarios_rental_area")
        ),
        sa.CheckConstraint(
            "exit_method IN ('appreciation', 'cap_rate')",
            name=op.f("ck_marketing_rental_scenarios_rental_exit"),
        ),
        sa.CheckConstraint(
            "mode IN ('long_term', 'short_term')",
            name=op.f("ck_marketing_rental_scenarios_rental_mode"),
        ),
        sa.CheckConstraint(
            "acquisition_cost_percent >= 0 AND acquisition_cost_percent <= 100",
            name=op.f("ck_marketing_rental_scenarios_acquisition_cost_percent"),
        ),
        sa.CheckConstraint(
            "annual_expense_per_sqm >= 0",
            name=op.f("ck_marketing_rental_scenarios_annual_expense_per_sqm"),
        ),
        sa.CheckConstraint(
            "annual_rent_per_sqm >= 0",
            name=op.f("ck_marketing_rental_scenarios_annual_rent_per_sqm"),
        ),
        sa.CheckConstraint(
            "appreciation_percent > -100 AND appreciation_percent <= 100",
            name=op.f("ck_marketing_rental_scenarios_appreciation_percent"),
        ),
        sa.CheckConstraint(
            "discount_percent >= 0 AND discount_percent <= 100",
            name=op.f("ck_marketing_rental_scenarios_discount_percent"),
        ),
        sa.CheckConstraint(
            "exit_cap_percent > 0 AND exit_cap_percent <= 100",
            name=op.f("ck_marketing_rental_scenarios_exit_cap_percent"),
        ),
        sa.CheckConstraint(
            "expense_growth_percent > -100 AND expense_growth_percent <= 100",
            name=op.f("ck_marketing_rental_scenarios_expense_growth_percent"),
        ),
        sa.CheckConstraint(
            "income_growth_percent > -100 AND income_growth_percent <= 100",
            name=op.f("ck_marketing_rental_scenarios_income_growth_percent"),
        ),
        sa.CheckConstraint(
            "price_override IS NULL OR (price_override > 0 AND unit_id IS NOT NULL)",
            name=op.f("ck_marketing_rental_scenarios_rental_price"),
        ),
        sa.CheckConstraint(
            "selling_cost_percent >= 0 AND selling_cost_percent <= 100",
            name=op.f("ck_marketing_rental_scenarios_selling_cost_percent"),
        ),
        sa.CheckConstraint(
            "setup_cost >= 0", name=op.f("ck_marketing_rental_scenarios_setup_cost")
        ),
        sa.CheckConstraint(
            "vacancy_percent >= 0 AND vacancy_percent <= 100",
            name=op.f("ck_marketing_rental_scenarios_vacancy_percent"),
        ),
        sa.ForeignKeyConstraint(
            ["currency_id"],
            ["currencies.id"],
            name=op.f("fk_marketing_rental_scenarios_currency_id_currencies"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_marketing_rental_scenarios_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["unit_id"],
            ["units.id"],
            name=op.f("fk_marketing_rental_scenarios_unit_id_units"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_marketing_rental_scenarios")),
    )
    op.create_index(
        op.f("ix_marketing_rental_scenarios_project_id"),
        "marketing_rental_scenarios",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "uq_marketing_rental_default",
        "marketing_rental_scenarios",
        ["project_id", "mode"],
        unique=True,
        postgresql_where=sa.text("NOT is_deleted AND unit_id IS NULL"),
    )
    op.create_index(
        "uq_marketing_rental_unit",
        "marketing_rental_scenarios",
        ["project_id", "unit_id", "mode"],
        unique=True,
        postgresql_where=sa.text("NOT is_deleted AND unit_id IS NOT NULL"),
    )


def downgrade() -> None:
    """Refuse data loss; rollback can leave the additive tables in place."""
    connection = op.get_bind()
    for table in ("marketing_content", "marketing_indicators", "marketing_rental_scenarios"):
        if connection.execute(sa.text(f"SELECT EXISTS (SELECT 1 FROM {table})")).scalar():
            raise RuntimeError("Marketing history exists; export and retain it before downgrade.")
    op.drop_index(
        "uq_marketing_rental_unit",
        table_name="marketing_rental_scenarios",
        postgresql_where=sa.text("NOT is_deleted AND unit_id IS NOT NULL"),
    )
    op.drop_index(
        "uq_marketing_rental_default",
        table_name="marketing_rental_scenarios",
        postgresql_where=sa.text("NOT is_deleted AND unit_id IS NULL"),
    )
    op.drop_index(
        op.f("ix_marketing_rental_scenarios_project_id"), table_name="marketing_rental_scenarios"
    )
    op.drop_table("marketing_rental_scenarios")
    op.drop_index(op.f("ix_marketing_indicators_project_id"), table_name="marketing_indicators")
    op.drop_table("marketing_indicators")
    op.drop_index(
        "uq_marketing_content_live",
        table_name="marketing_content",
        postgresql_where=sa.text("NOT is_deleted"),
    )
    op.drop_index(op.f("ix_marketing_content_project_id"), table_name="marketing_content")
    op.drop_table("marketing_content")
