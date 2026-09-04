"""Cashflow: the governed forecast, the cash this module owns, and escrow.

Seven tables, and what is *absent* from them is the design. No receipt, refund,
construction payment or buyer instalment is copied here — those rows stay with
the modules that govern them, and cashflow reads them through named contracts.
What this revision creates is the cash the platform has no other record of and
the governed statement of when Finance expects the rest of it to move.

``cashflow_forecast_versions`` carries the same partial unique indexes the
construction forecast uses: one active and one open per project, held by the
database rather than by a service that remembers to check. It pins the
construction forecast version it schedules through a project-safe composite
foreign key, so a cashflow forecast can never cite another project's costs.

``cashflow_forecast_lines`` carries a cross-column CHECK rather than four
validators: a construction line must name a cost code (or the reconciliation
against the construction forecast has nothing to group by), a development line
must not, an unsold-customer line is an inflow, and a financing line's direction
must match its type. Those are facts about the transaction, not choices on a
form.

``cashflow_receipt_restrictions`` allows one standing restriction per receipt
through a partial unique index. Two would each be validated against the receipt
alone and together exceed it — the classic escrow over-restriction, closed at
the schema rather than in the service that writes them.

Both movement tables refuse a confirmer who is the recorder, by user identifier.
A role comparison would let one person holding two roles confirm their own
disbursement, which is not a second pair of eyes.

Revision ID: 0011_cashflow_reporting
Revises: 0010_construction_source_kind
Create Date: 2026-09-04 08:45:15.216874+00:00

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_cashflow_reporting"
down_revision: str | Sequence[str] | None = "0010_construction_source_kind"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply this revision."""
    op.create_table(
        "cashflow_financing_movements",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("movement_reference", sa.String(length=32), nullable=False),
        sa.Column("movement_type", sa.String(length=32), nullable=False),
        sa.Column("flow_direction", sa.String(length=16), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("currency_id", sa.UUID(), nullable=False),
        sa.Column("movement_date", sa.Date(), nullable=False),
        sa.Column("value_date", sa.Date(), nullable=True),
        sa.Column("counterparty_reference", sa.String(length=200), nullable=True),
        sa.Column("facility_reference", sa.String(length=200), nullable=True),
        sa.Column("bank_reference", sa.String(length=200), nullable=True),
        sa.Column("evidence_reference", sa.String(length=500), nullable=True),
        sa.Column("notes", sa.String(length=2000), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("recorded_by_user_id", sa.UUID(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_by_user_id", sa.UUID(), nullable=True),
        sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reversed_by_user_id", sa.UUID(), nullable=True),
        sa.Column("reversal_reason", sa.String(length=1000), nullable=True),
        sa.CheckConstraint(
            "(movement_type IN ('equity_contribution', 'debt_drawdown', 'guarantee_cash_release') "
            "AND flow_direction = 'inflow') OR (movement_type IN ('equity_distribution', "
            "'debt_fee', 'interest_payment', 'principal_repayment', 'guarantee_cash_posting') "
            "AND flow_direction = 'outflow')",
            name=op.f("ck_cashflow_financing_movements_direction_matches_type"),
        ),
        sa.CheckConstraint(
            "flow_direction IN ('inflow', 'outflow')",
            name=op.f("ck_cashflow_financing_movements_direction_ok"),
        ),
        sa.CheckConstraint(
            "movement_type IN ('equity_contribution', 'debt_drawdown', 'guarantee_cash_release', "
            "'equity_distribution', 'debt_fee', 'interest_payment', 'principal_repayment', "
            "'guarantee_cash_posting')",
            name=op.f("ck_cashflow_financing_movements_movement_type_ok"),
        ),
        sa.CheckConstraint(
            "status <> 'confirmed' OR (confirmed_at IS NOT NULL "
            "AND confirmed_by_user_id IS NOT NULL)",
            name=op.f("ck_cashflow_financing_movements_confirmed_has_actor"),
        ),
        sa.CheckConstraint(
            "status <> 'reversed' OR (reversed_at IS NOT NULL AND reversed_by_user_id IS NOT NULL "
            "AND reversal_reason IS NOT NULL)",
            name=op.f("ck_cashflow_financing_movements_reversed_has_reason"),
        ),
        sa.CheckConstraint(
            "status IN ('recorded', 'confirmed', 'reversed')",
            name=op.f("ck_cashflow_financing_movements_status_ok"),
        ),
        sa.CheckConstraint(
            "amount > 0", name=op.f("ck_cashflow_financing_movements_amount_positive")
        ),
        sa.CheckConstraint(
            "confirmed_by_user_id IS NULL OR confirmed_by_user_id <> recorded_by_user_id",
            name=op.f("ck_cashflow_financing_movements_confirmer_is_not_recorder"),
        ),
        sa.ForeignKeyConstraint(
            ["confirmed_by_user_id"],
            ["users.id"],
            name=op.f("fk_cashflow_financing_movements_confirmed_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["currency_id"],
            ["currencies.id"],
            name=op.f("fk_cashflow_financing_movements_currency_id_currencies"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_cashflow_financing_movements_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["recorded_by_user_id"],
            ["users.id"],
            name=op.f("fk_cashflow_financing_movements_recorded_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reversed_by_user_id"],
            ["users.id"],
            name=op.f("fk_cashflow_financing_movements_reversed_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cashflow_financing_movements")),
        sa.UniqueConstraint("id", "project_id", name="cf_fin_movement_project"),
        sa.UniqueConstraint("project_id", "movement_reference", name="uq_cf_fin_reference"),
    )
    op.create_index(
        op.f("ix_cashflow_financing_movements_project_id"),
        "cashflow_financing_movements",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_cf_fin_movements_date",
        "cashflow_financing_movements",
        ["project_id", "movement_date"],
        unique=False,
    )
    op.create_index(
        "ix_cf_fin_movements_project_status",
        "cashflow_financing_movements",
        ["project_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_cf_fin_movements_type",
        "cashflow_financing_movements",
        ["project_id", "movement_type"],
        unique=False,
    )
    op.create_table(
        "cashflow_development_movements",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("movement_reference", sa.String(length=32), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("currency_id", sa.UUID(), nullable=False),
        sa.Column("movement_date", sa.Date(), nullable=False),
        sa.Column("value_date", sa.Date(), nullable=True),
        sa.Column("phase_id", sa.UUID(), nullable=True),
        sa.Column("counterparty_reference", sa.String(length=200), nullable=True),
        sa.Column("invoice_reference", sa.String(length=200), nullable=True),
        sa.Column("bank_reference", sa.String(length=200), nullable=True),
        sa.Column("evidence_reference", sa.String(length=500), nullable=True),
        sa.Column("notes", sa.String(length=2000), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("recorded_by_user_id", sa.UUID(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_by_user_id", sa.UUID(), nullable=True),
        sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reversed_by_user_id", sa.UUID(), nullable=True),
        sa.Column("reversal_reason", sa.String(length=1000), nullable=True),
        sa.CheckConstraint(
            "category IN ('land_acquisition', 'land_fees', 'design', 'consultants', 'permits', "
            "'insurance', 'developer_overhead', 'marketing', 'commissions', 'tax', 'handover', "
            "'other')",
            name=op.f("ck_cashflow_development_movements_category_ok"),
        ),
        sa.CheckConstraint(
            "status <> 'confirmed' OR (confirmed_at IS NOT NULL "
            "AND confirmed_by_user_id IS NOT NULL)",
            name=op.f("ck_cashflow_development_movements_confirmed_has_actor"),
        ),
        sa.CheckConstraint(
            "status <> 'reversed' OR (reversed_at IS NOT NULL AND reversed_by_user_id IS NOT NULL "
            "AND reversal_reason IS NOT NULL)",
            name=op.f("ck_cashflow_development_movements_reversed_has_reason"),
        ),
        sa.CheckConstraint(
            "status IN ('recorded', 'confirmed', 'reversed')",
            name=op.f("ck_cashflow_development_movements_status_ok"),
        ),
        sa.CheckConstraint(
            "amount > 0", name=op.f("ck_cashflow_development_movements_amount_positive")
        ),
        sa.CheckConstraint(
            "confirmed_by_user_id IS NULL OR confirmed_by_user_id <> recorded_by_user_id",
            name=op.f("ck_cashflow_development_movements_confirmer_is_not_recorder"),
        ),
        sa.ForeignKeyConstraint(
            ["confirmed_by_user_id"],
            ["users.id"],
            name=op.f("fk_cashflow_development_movements_confirmed_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["currency_id"],
            ["currencies.id"],
            name=op.f("fk_cashflow_development_movements_currency_id_currencies"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["phase_id", "project_id"],
            ["phases.id", "phases.project_id"],
            name="phase",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_cashflow_development_movements_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["recorded_by_user_id"],
            ["users.id"],
            name=op.f("fk_cashflow_development_movements_recorded_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reversed_by_user_id"],
            ["users.id"],
            name=op.f("fk_cashflow_development_movements_reversed_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cashflow_development_movements")),
        sa.UniqueConstraint("id", "project_id", name="cf_dev_movement_project"),
        sa.UniqueConstraint("project_id", "movement_reference", name="uq_cf_dev_reference"),
    )
    op.create_index(
        op.f("ix_cashflow_development_movements_project_id"),
        "cashflow_development_movements",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_cf_dev_movements_date",
        "cashflow_development_movements",
        ["project_id", "movement_date"],
        unique=False,
    )
    op.create_index(
        "ix_cf_dev_movements_project_status",
        "cashflow_development_movements",
        ["project_id", "status"],
        unique=False,
    )
    op.create_table(
        "cashflow_forecast_versions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("currency_id", sa.UUID(), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("forecast_start_month", sa.Date(), nullable=False),
        sa.Column("forecast_end_month", sa.Date(), nullable=False),
        sa.Column("opening_unrestricted_cash", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("opening_restricted_cash", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("discount_rate_per_period", sa.Numeric(precision=9, scale=6), nullable=False),
        sa.Column("source_version_id", sa.UUID(), nullable=True),
        sa.Column("construction_forecast_version_id", sa.UUID(), nullable=True),
        sa.Column("change_reason", sa.String(length=1000), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_by_user_id", sa.UUID(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_user_id", sa.UUID(), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_by_user_id", sa.UUID(), nullable=True),
        sa.Column("rejection_reason", sa.String(length=1000), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_by_user_id", sa.UUID(), nullable=True),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status <> 'rejected' OR (rejected_at IS NOT NULL AND rejected_by_user_id IS NOT NULL "
            "AND rejection_reason IS NOT NULL)",
            name=op.f("ck_cashflow_forecast_versions_rejected_shape"),
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'submitted', 'approved', 'active', 'superseded', 'rejected')",
            name=op.f("ck_cashflow_forecast_versions_status_ok"),
        ),
        sa.CheckConstraint(
            "status NOT IN ('active', 'superseded') OR (activated_at IS NOT NULL "
            "AND activated_by_user_id IS NOT NULL)",
            name=op.f("ck_cashflow_forecast_versions_activated_shape"),
        ),
        sa.CheckConstraint(
            "status NOT IN ('approved', 'active', 'superseded') OR (approved_at IS NOT NULL "
            "AND approved_by_user_id IS NOT NULL)",
            name=op.f("ck_cashflow_forecast_versions_approved_shape"),
        ),
        sa.CheckConstraint(
            "EXTRACT(DAY FROM forecast_end_month) = 1",
            name=op.f("ck_cashflow_forecast_versions_end_canonical"),
        ),
        sa.CheckConstraint(
            "EXTRACT(DAY FROM forecast_start_month) = 1",
            name=op.f("ck_cashflow_forecast_versions_start_canonical"),
        ),
        sa.CheckConstraint(
            "discount_rate_per_period >= 0",
            name=op.f("ck_cashflow_forecast_versions_discount_rate_nonneg"),
        ),
        sa.CheckConstraint(
            "forecast_end_month >= forecast_start_month",
            name=op.f("ck_cashflow_forecast_versions_horizon_ordered"),
        ),
        sa.CheckConstraint(
            "length(change_reason) > 0", name=op.f("ck_cashflow_forecast_versions_reason_present")
        ),
        sa.CheckConstraint(
            "opening_restricted_cash >= 0",
            name=op.f("ck_cashflow_forecast_versions_opening_restricted_nonneg"),
        ),
        sa.CheckConstraint(
            "opening_unrestricted_cash >= 0",
            name=op.f("ck_cashflow_forecast_versions_opening_unrestricted_nonneg"),
        ),
        sa.CheckConstraint(
            "source_version_id IS NULL OR source_version_id <> id",
            name=op.f("ck_cashflow_forecast_versions_source_not_self"),
        ),
        sa.CheckConstraint(
            "version_number >= 1", name=op.f("ck_cashflow_forecast_versions_number_positive")
        ),
        sa.ForeignKeyConstraint(
            ["activated_by_user_id"],
            ["users.id"],
            name=op.f("fk_cashflow_forecast_versions_activated_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["approved_by_user_id"],
            ["users.id"],
            name=op.f("fk_cashflow_forecast_versions_approved_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["construction_forecast_version_id", "project_id"],
            ["construction_forecast_versions.id", "construction_forecast_versions.project_id"],
            name="construction_forecast",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_cashflow_forecast_versions_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["currency_id"],
            ["currencies.id"],
            name=op.f("fk_cashflow_forecast_versions_currency_id_currencies"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_cashflow_forecast_versions_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["rejected_by_user_id"],
            ["users.id"],
            name=op.f("fk_cashflow_forecast_versions_rejected_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_version_id", "project_id"],
            ["cashflow_forecast_versions.id", "cashflow_forecast_versions.project_id"],
            name="source_version",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["submitted_by_user_id"],
            ["users.id"],
            name=op.f("fk_cashflow_forecast_versions_submitted_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cashflow_forecast_versions")),
        sa.UniqueConstraint("id", "project_id", name="cf_forecast_project"),
        sa.UniqueConstraint("project_id", "version_number", name="uq_cf_forecast_number"),
    )
    op.create_index(
        op.f("ix_cashflow_forecast_versions_project_id"),
        "cashflow_forecast_versions",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_cf_forecasts_project_status",
        "cashflow_forecast_versions",
        ["project_id", "status"],
        unique=False,
    )
    op.create_index(
        "uq_cf_forecasts_one_active",
        "cashflow_forecast_versions",
        ["project_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index(
        "uq_cf_forecasts_one_open",
        "cashflow_forecast_versions",
        ["project_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('draft', 'submitted', 'approved')"),
    )
    op.create_table(
        "cashflow_forecast_lines",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("forecast_version_id", sa.UUID(), nullable=False),
        sa.Column("period_month", sa.Date(), nullable=False),
        sa.Column("flow_direction", sa.String(length=16), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("source_kind", sa.String(length=24), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("phase_id", sa.UUID(), nullable=True),
        sa.Column("construction_cost_code_id", sa.UUID(), nullable=True),
        sa.Column("note", sa.String(length=2000), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(source_kind = 'construction' AND category = 'construction' "
            "AND construction_cost_code_id IS NOT NULL AND flow_direction = 'outflow') "
            "OR (source_kind = 'development' AND category IN ('land_acquisition', 'land_fees', "
            "'design', 'consultants', 'permits', 'insurance', 'developer_overhead', 'marketing', "
            "'commissions', 'tax', 'handover', 'other') AND construction_cost_code_id IS NULL "
            "AND flow_direction = 'outflow') OR (source_kind = 'unsold_customer' "
            "AND category = 'customer_collection' AND construction_cost_code_id IS NULL "
            "AND flow_direction = 'inflow') OR (source_kind = 'financing' "
            "AND category IN ('equity_contribution', 'debt_drawdown', 'guarantee_cash_release', "
            "'equity_distribution', 'debt_fee', 'interest_payment', 'principal_repayment', "
            "'guarantee_cash_posting') AND construction_cost_code_id IS NULL)",
            name=op.f("ck_cashflow_forecast_lines_source_shape_ok"),
        ),
        sa.CheckConstraint(
            "category IN ('customer_collection', 'construction', 'land_acquisition', 'land_fees', "
            "'design', 'consultants', 'permits', 'insurance', 'developer_overhead', 'marketing', "
            "'commissions', 'tax', 'handover', 'other', 'equity_contribution', 'debt_drawdown', "
            "'guarantee_cash_release', 'equity_distribution', 'debt_fee', 'interest_payment', "
            "'principal_repayment', 'guarantee_cash_posting')",
            name=op.f("ck_cashflow_forecast_lines_category_ok"),
        ),
        sa.CheckConstraint(
            "flow_direction IN ('inflow', 'outflow')",
            name=op.f("ck_cashflow_forecast_lines_direction_ok"),
        ),
        sa.CheckConstraint(
            "source_kind IN ('unsold_customer', 'development', 'construction', 'financing')",
            name=op.f("ck_cashflow_forecast_lines_source_kind_ok"),
        ),
        sa.CheckConstraint(
            "EXTRACT(DAY FROM period_month) = 1",
            name=op.f("ck_cashflow_forecast_lines_month_canonical"),
        ),
        sa.CheckConstraint("amount >= 0", name=op.f("ck_cashflow_forecast_lines_amount_nonneg")),
        sa.ForeignKeyConstraint(
            ["construction_cost_code_id", "project_id"],
            ["construction_cost_codes.id", "construction_cost_codes.project_id"],
            name="cost_code",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["forecast_version_id", "project_id"],
            ["cashflow_forecast_versions.id", "cashflow_forecast_versions.project_id"],
            name="version",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["phase_id", "project_id"],
            ["phases.id", "phases.project_id"],
            name="phase",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cashflow_forecast_lines")),
        sa.UniqueConstraint("id", "project_id", name="cf_forecast_line_project"),
    )
    op.create_index(
        "ix_cf_forecast_lines_cost_code",
        "cashflow_forecast_lines",
        ["forecast_version_id", "construction_cost_code_id"],
        unique=False,
    )
    op.create_index(
        "ix_cf_forecast_lines_version_month",
        "cashflow_forecast_lines",
        ["forecast_version_id", "period_month"],
        unique=False,
    )
    op.create_index(
        "ix_cf_forecast_lines_version_source",
        "cashflow_forecast_lines",
        ["forecast_version_id", "source_kind"],
        unique=False,
    )
    op.create_table(
        "cashflow_receipt_restrictions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("receipt_id", sa.UUID(), nullable=False),
        sa.Column("restricted_amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.Column("source_reference", sa.String(length=200), nullable=True),
        sa.Column("notes", sa.String(length=2000), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("recorded_by_user_id", sa.UUID(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_by_user_id", sa.UUID(), nullable=True),
        sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reversed_by_user_id", sa.UUID(), nullable=True),
        sa.Column("reversal_reason", sa.String(length=1000), nullable=True),
        sa.CheckConstraint(
            "status <> 'confirmed' OR (confirmed_at IS NOT NULL "
            "AND confirmed_by_user_id IS NOT NULL)",
            name=op.f("ck_cashflow_receipt_restrictions_confirmed_has_actor"),
        ),
        sa.CheckConstraint(
            "status <> 'reversed' OR (reversed_at IS NOT NULL AND reversed_by_user_id IS NOT NULL "
            "AND reversal_reason IS NOT NULL)",
            name=op.f("ck_cashflow_receipt_restrictions_reversed_has_reason"),
        ),
        sa.CheckConstraint(
            "status IN ('recorded', 'confirmed', 'reversed')",
            name=op.f("ck_cashflow_receipt_restrictions_status_ok"),
        ),
        sa.CheckConstraint(
            "length(reason) > 0", name=op.f("ck_cashflow_receipt_restrictions_reason_present")
        ),
        sa.CheckConstraint(
            "restricted_amount >= 0", name=op.f("ck_cashflow_receipt_restrictions_amount_nonneg")
        ),
        sa.ForeignKeyConstraint(
            ["confirmed_by_user_id"],
            ["users.id"],
            name=op.f("fk_cashflow_receipt_restrictions_confirmed_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_cashflow_receipt_restrictions_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["receipt_id", "project_id"],
            ["collection_receipts.id", "collection_receipts.project_id"],
            name="receipt",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["recorded_by_user_id"],
            ["users.id"],
            name=op.f("fk_cashflow_receipt_restrictions_recorded_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reversed_by_user_id"],
            ["users.id"],
            name=op.f("fk_cashflow_receipt_restrictions_reversed_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cashflow_receipt_restrictions")),
        sa.UniqueConstraint("id", "project_id", name="cf_restriction_project"),
    )
    op.create_index(
        op.f("ix_cashflow_receipt_restrictions_project_id"),
        "cashflow_receipt_restrictions",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_cf_restrictions_project_status",
        "cashflow_receipt_restrictions",
        ["project_id", "status"],
        unique=False,
    )
    op.create_index(
        "uq_cf_restriction_one_standing",
        "cashflow_receipt_restrictions",
        ["receipt_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('recorded', 'confirmed')"),
    )
    op.create_table(
        "cashflow_restriction_releases",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("restriction_id", sa.UUID(), nullable=False),
        sa.Column("release_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("certification_reference", sa.String(length=200), nullable=True),
        sa.Column("evidence_reference", sa.String(length=500), nullable=True),
        sa.Column("notes", sa.String(length=2000), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("recorded_by_user_id", sa.UUID(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_by_user_id", sa.UUID(), nullable=True),
        sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reversed_by_user_id", sa.UUID(), nullable=True),
        sa.Column("reversal_reason", sa.String(length=1000), nullable=True),
        sa.CheckConstraint(
            "status <> 'confirmed' OR (confirmed_at IS NOT NULL "
            "AND confirmed_by_user_id IS NOT NULL)",
            name=op.f("ck_cashflow_restriction_releases_confirmed_has_actor"),
        ),
        sa.CheckConstraint(
            "status <> 'reversed' OR (reversed_at IS NOT NULL AND reversed_by_user_id IS NOT NULL "
            "AND reversal_reason IS NOT NULL)",
            name=op.f("ck_cashflow_restriction_releases_reversed_has_reason"),
        ),
        sa.CheckConstraint(
            "status IN ('recorded', 'confirmed', 'reversed')",
            name=op.f("ck_cashflow_restriction_releases_status_ok"),
        ),
        sa.CheckConstraint(
            "amount > 0", name=op.f("ck_cashflow_restriction_releases_amount_positive")
        ),
        sa.CheckConstraint(
            "confirmed_by_user_id IS NULL OR confirmed_by_user_id <> recorded_by_user_id",
            name=op.f("ck_cashflow_restriction_releases_confirmer_is_not_recorder"),
        ),
        sa.ForeignKeyConstraint(
            ["confirmed_by_user_id"],
            ["users.id"],
            name=op.f("fk_cashflow_restriction_releases_confirmed_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_cashflow_restriction_releases_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["recorded_by_user_id"],
            ["users.id"],
            name=op.f("fk_cashflow_restriction_releases_recorded_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["restriction_id", "project_id"],
            ["cashflow_receipt_restrictions.id", "cashflow_receipt_restrictions.project_id"],
            name="restriction",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reversed_by_user_id"],
            ["users.id"],
            name=op.f("fk_cashflow_restriction_releases_reversed_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cashflow_restriction_releases")),
        sa.UniqueConstraint("id", "project_id", name="cf_release_project"),
    )
    op.create_index(
        op.f("ix_cashflow_restriction_releases_project_id"),
        "cashflow_restriction_releases",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_cf_releases_project_date",
        "cashflow_restriction_releases",
        ["project_id", "release_date"],
        unique=False,
    )
    op.create_index(
        "ix_cf_releases_restriction_status",
        "cashflow_restriction_releases",
        ["restriction_id", "status"],
        unique=False,
    )
    op.create_table(
        "cashflow_customer_schedule_snapshots",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("forecast_version_id", sa.UUID(), nullable=False),
        sa.Column("payment_plan_version_id", sa.UUID(), nullable=False),
        sa.Column("installment_id", sa.UUID(), nullable=False),
        sa.Column("sale_contract_id", sa.UUID(), nullable=False),
        sa.Column("unit_id", sa.UUID(), nullable=True),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("contractual_due_date", sa.Date(), nullable=True),
        sa.Column("forecast_due_date", sa.Date(), nullable=True),
        sa.Column("actual_due_date", sa.Date(), nullable=True),
        sa.Column("chosen_forecast_date", sa.Date(), nullable=False),
        sa.Column("trigger_type", sa.String(length=32), nullable=False),
        sa.Column("trigger_status", sa.String(length=24), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "amount >= 0", name=op.f("ck_cashflow_customer_schedule_snapshots_amount_nonneg")
        ),
        sa.ForeignKeyConstraint(
            ["forecast_version_id", "project_id"],
            ["cashflow_forecast_versions.id", "cashflow_forecast_versions.project_id"],
            name="version",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["installment_id", "project_id"],
            ["payment_plan_installments.id", "payment_plan_installments.project_id"],
            name="installment",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["payment_plan_version_id", "project_id"],
            ["payment_plan_versions.id", "payment_plan_versions.project_id"],
            name="plan_version",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["sale_contract_id", "project_id"],
            ["sale_contracts.id", "sale_contracts.project_id"],
            name="sale",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cashflow_customer_schedule_snapshots")),
        sa.UniqueConstraint(
            "forecast_version_id", "installment_id", name="uq_cf_snapshot_installment"
        ),
    )
    op.create_index(
        "ix_cf_snapshots_sale",
        "cashflow_customer_schedule_snapshots",
        ["forecast_version_id", "sale_contract_id"],
        unique=False,
    )
    op.create_index(
        "ix_cf_snapshots_version_date",
        "cashflow_customer_schedule_snapshots",
        ["forecast_version_id", "chosen_forecast_date"],
        unique=False,
    )


def downgrade() -> None:
    """Revert this revision, dropping every table it created.

    Nothing here is shared with another domain, so the drop order is simply
    the reverse of creation and no other module loses a column.
    """
    op.drop_index("ix_cf_snapshots_version_date", table_name="cashflow_customer_schedule_snapshots")
    op.drop_index("ix_cf_snapshots_sale", table_name="cashflow_customer_schedule_snapshots")
    op.drop_table("cashflow_customer_schedule_snapshots")
    op.drop_index("ix_cf_releases_restriction_status", table_name="cashflow_restriction_releases")
    op.drop_index("ix_cf_releases_project_date", table_name="cashflow_restriction_releases")
    op.drop_index(
        op.f("ix_cashflow_restriction_releases_project_id"),
        table_name="cashflow_restriction_releases",
    )
    op.drop_table("cashflow_restriction_releases")
    op.drop_index(
        "uq_cf_restriction_one_standing",
        table_name="cashflow_receipt_restrictions",
        postgresql_where=sa.text("status IN ('recorded', 'confirmed')"),
    )
    op.drop_index("ix_cf_restrictions_project_status", table_name="cashflow_receipt_restrictions")
    op.drop_index(
        op.f("ix_cashflow_receipt_restrictions_project_id"),
        table_name="cashflow_receipt_restrictions",
    )
    op.drop_table("cashflow_receipt_restrictions")
    op.drop_index("ix_cf_forecast_lines_version_source", table_name="cashflow_forecast_lines")
    op.drop_index("ix_cf_forecast_lines_version_month", table_name="cashflow_forecast_lines")
    op.drop_index("ix_cf_forecast_lines_cost_code", table_name="cashflow_forecast_lines")
    op.drop_table("cashflow_forecast_lines")
    op.drop_index(
        "uq_cf_forecasts_one_open",
        table_name="cashflow_forecast_versions",
        postgresql_where=sa.text("status IN ('draft', 'submitted', 'approved')"),
    )
    op.drop_index(
        "uq_cf_forecasts_one_active",
        table_name="cashflow_forecast_versions",
        postgresql_where=sa.text("status = 'active'"),
    )
    op.drop_index("ix_cf_forecasts_project_status", table_name="cashflow_forecast_versions")
    op.drop_index(
        op.f("ix_cashflow_forecast_versions_project_id"), table_name="cashflow_forecast_versions"
    )
    op.drop_table("cashflow_forecast_versions")
    op.drop_index("ix_cf_dev_movements_project_status", table_name="cashflow_development_movements")
    op.drop_index("ix_cf_dev_movements_date", table_name="cashflow_development_movements")
    op.drop_index(
        op.f("ix_cashflow_development_movements_project_id"),
        table_name="cashflow_development_movements",
    )
    op.drop_table("cashflow_development_movements")
    op.drop_index("ix_cf_fin_movements_type", table_name="cashflow_financing_movements")
    op.drop_index("ix_cf_fin_movements_project_status", table_name="cashflow_financing_movements")
    op.drop_index("ix_cf_fin_movements_date", table_name="cashflow_financing_movements")
    op.drop_index(
        op.f("ix_cashflow_financing_movements_project_id"),
        table_name="cashflow_financing_movements",
    )
    op.drop_table("cashflow_financing_movements")
