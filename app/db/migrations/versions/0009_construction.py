"""Construction control: budget, commitment, certification, cash and forecast.

Sixteen tables and one column on somebody else's, which is the ratio worth
reading twice. The sixteen are here because budget, commitment, certified work,
invoice liability and paid cash are five different facts with five different
approvers, and a schema that stored them as one "construction cost" would make
the difference between them unaskable. The one column is provenance: a unit
economics cost pool may now name the construction forecast its hard-cost amount
came from.

What is deliberately absent is longer than what is here. No foreign key from
``payment_plan_installments`` into this module — a buyer's schedule still points
at a milestone by its code, a stable handle rather than a relationship, so a
plan written before construction existed keeps working and neither module
imports the other. No construction columns on ``units``: the delivery status a
build drives already has an owner in inventory, reached through its public
contract. No ``paid``, ``balance``, ``revised_contract_value``,
``cumulative_certified`` or ``retention_balance`` anywhere, because each is a sum
over immutable rows and a stored sum is a number waiting to disagree with them.

Creation order follows the references. Cost codes first, because every financial
row points at one. Then the parents that own lifecycles — budget versions,
contracts, certificates, payments, variations, milestones, forecast versions —
then the lines and allocations that hang off them, and last the alteration to
``unit_economics_cost_pools``, which cannot name a forecast version before one
can exist. The downgrade reverses exactly that: the cost pool loses its
provenance column and its two shape checks, and the sixteen tables drop in the
opposite order, leaving unit economics, payment plans, collections, sales,
pricing, inventory and projects precisely as 0008 left them.

Revision ID: 0009_construction
Revises: 0008_unit_economics
Create Date: 2026-09-03 07:27:59.359138+00:00

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_construction"
down_revision: str | Sequence[str] | None = "0008_unit_economics"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply this revision."""
    op.create_table(
        "construction_budget_versions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("currency_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("source_version_id", sa.UUID(), nullable=True),
        sa.Column("change_reason", sa.String(length=1000), nullable=False),
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
            "status IN ('draft', 'submitted', 'approved', 'active', 'superseded', 'rejected')",
            name=op.f("ck_construction_budget_versions_status_ok"),
        ),
        sa.CheckConstraint(
            "length(change_reason) > 0", name=op.f("ck_construction_budget_versions_reason_present")
        ),
        sa.CheckConstraint(
            "version_number >= 1", name=op.f("ck_construction_budget_versions_number_positive")
        ),
        sa.ForeignKeyConstraint(
            ["activated_by_user_id"],
            ["users.id"],
            name=op.f("fk_construction_budget_versions_activated_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["approved_by_user_id"],
            ["users.id"],
            name=op.f("fk_construction_budget_versions_approved_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_construction_budget_versions_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["currency_id"],
            ["currencies.id"],
            name=op.f("fk_construction_budget_versions_currency_id_currencies"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_construction_budget_versions_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["rejected_by_user_id"],
            ["users.id"],
            name=op.f("fk_construction_budget_versions_rejected_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["submitted_by_user_id"],
            ["users.id"],
            name=op.f("fk_construction_budget_versions_submitted_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_construction_budget_versions")),
        sa.UniqueConstraint("id", "project_id", name="cx_budget_project"),
        sa.UniqueConstraint("project_id", "version_number", name="uq_cx_budget_number"),
    )
    op.create_index(
        op.f("ix_construction_budget_versions_project_id"),
        "construction_budget_versions",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_cx_budgets_project_status",
        "construction_budget_versions",
        ["project_id", "status"],
        unique=False,
    )
    op.create_index(
        "uq_cx_budgets_one_active",
        "construction_budget_versions",
        ["project_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index(
        "uq_cx_budgets_one_open",
        "construction_budget_versions",
        ["project_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('draft', 'submitted', 'approved')"),
    )
    op.create_table(
        "construction_contracts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("contract_number", sa.String(length=64), nullable=False),
        sa.Column("contract_type", sa.String(length=24), nullable=False),
        sa.Column("vendor_name", sa.String(length=200), nullable=False),
        sa.Column("vendor_registration_reference", sa.String(length=120), nullable=True),
        sa.Column("vendor_tax_reference", sa.String(length=120), nullable=True),
        sa.Column("vendor_contact_reference", sa.String(length=200), nullable=True),
        sa.Column("currency_id", sa.UUID(), nullable=False),
        sa.Column(
            "original_contract_value_ex_tax", sa.Numeric(precision=18, scale=2), nullable=False
        ),
        sa.Column("advance_entitlement_amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("retention_rate_fraction", sa.Numeric(precision=9, scale=6), nullable=False),
        sa.Column("tax_rate_fraction", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("payment_terms", sa.String(length=500), nullable=True),
        sa.Column("planned_start_date", sa.Date(), nullable=True),
        sa.Column("planned_completion_date", sa.Date(), nullable=True),
        sa.Column("actual_start_date", sa.Date(), nullable=True),
        sa.Column("actual_completion_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("notes", sa.String(length=2000), nullable=True),
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
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_by_user_id", sa.UUID(), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_by_user_id", sa.UUID(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("terminated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("termination_reason", sa.String(length=1000), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_reason", sa.String(length=1000), nullable=True),
        sa.CheckConstraint(
            "contract_type IN ('works', 'consultancy', 'supply', 'purchase_order', 'other')",
            name=op.f("ck_construction_contracts_type_ok"),
        ),
        sa.CheckConstraint(
            "status <> 'cancelled' OR cancellation_reason IS NOT NULL",
            name=op.f("ck_construction_contracts_cancelled_has_reason"),
        ),
        sa.CheckConstraint(
            "status <> 'terminated' OR termination_reason IS NOT NULL",
            name=op.f("ck_construction_contracts_terminated_has_reason"),
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'submitted', 'active', 'completed', 'terminated', 'cancelled')",
            name=op.f("ck_construction_contracts_status_ok"),
        ),
        sa.CheckConstraint(
            "actual_completion_date IS NULL OR actual_start_date IS NULL"
            " OR actual_completion_date >= actual_start_date",
            name=op.f("ck_construction_contracts_actual_order"),
        ),
        sa.CheckConstraint(
            "advance_entitlement_amount >= 0", name=op.f("ck_construction_contracts_advance_nonneg")
        ),
        sa.CheckConstraint(
            "length(contract_number) > 0", name=op.f("ck_construction_contracts_number_present")
        ),
        sa.CheckConstraint(
            "length(vendor_name) > 0", name=op.f("ck_construction_contracts_vendor_present")
        ),
        sa.CheckConstraint(
            "original_contract_value_ex_tax >= 0",
            name=op.f("ck_construction_contracts_value_nonneg"),
        ),
        sa.CheckConstraint(
            "planned_completion_date IS NULL OR planned_start_date IS NULL"
            " OR planned_completion_date >= planned_start_date",
            name=op.f("ck_construction_contracts_planned_order"),
        ),
        sa.CheckConstraint(
            "retention_rate_fraction >= 0 AND retention_rate_fraction <= 1",
            name=op.f("ck_construction_contracts_retention_range"),
        ),
        sa.CheckConstraint(
            "tax_rate_fraction IS NULL OR (tax_rate_fraction >= 0 AND tax_rate_fraction <= 1)",
            name=op.f("ck_construction_contracts_tax_range"),
        ),
        sa.ForeignKeyConstraint(
            ["activated_by_user_id"],
            ["users.id"],
            name=op.f("fk_construction_contracts_activated_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_construction_contracts_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["currency_id"],
            ["currencies.id"],
            name=op.f("fk_construction_contracts_currency_id_currencies"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_construction_contracts_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["submitted_by_user_id"],
            ["users.id"],
            name=op.f("fk_construction_contracts_submitted_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_construction_contracts")),
        sa.UniqueConstraint("id", "project_id", name="cx_contract_project"),
        sa.UniqueConstraint("project_id", "contract_number", name="uq_cx_contract_number"),
    )
    op.create_index(
        op.f("ix_construction_contracts_project_id"),
        "construction_contracts",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_cx_contracts_project_status",
        "construction_contracts",
        ["project_id", "status"],
        unique=False,
    )
    op.create_table(
        "construction_certificates",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("contract_id", sa.UUID(), nullable=False),
        sa.Column("certificate_number", sa.String(length=64), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("certificate_date", sa.Date(), nullable=False),
        sa.Column("retention_release_amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("advance_recovery_amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("other_deductions_amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("tax_amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("certifier_name", sa.String(length=200), nullable=True),
        sa.Column("evidence_reference", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("notes", sa.String(length=2000), nullable=True),
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
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_by_user_id", sa.UUID(), nullable=True),
        sa.Column("certified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("certified_by_user_id", sa.UUID(), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_by_user_id", sa.UUID(), nullable=True),
        sa.Column("rejection_reason", sa.String(length=1000), nullable=True),
        sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reversed_by_user_id", sa.UUID(), nullable=True),
        sa.Column("reversal_reason", sa.String(length=1000), nullable=True),
        sa.CheckConstraint(
            "status <> 'rejected' OR rejection_reason IS NOT NULL",
            name=op.f("ck_construction_certificates_rejected_has_reason"),
        ),
        sa.CheckConstraint(
            "status <> 'reversed' OR reversal_reason IS NOT NULL",
            name=op.f("ck_construction_certificates_reversed_has_reason"),
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'submitted', 'certified', 'rejected', 'reversed')",
            name=op.f("ck_construction_certificates_status_ok"),
        ),
        sa.CheckConstraint(
            "advance_recovery_amount >= 0",
            name=op.f("ck_construction_certificates_recovery_nonneg"),
        ),
        sa.CheckConstraint(
            "length(certificate_number) > 0",
            name=op.f("ck_construction_certificates_number_present"),
        ),
        sa.CheckConstraint(
            "other_deductions_amount >= 0",
            name=op.f("ck_construction_certificates_deduction_nonneg"),
        ),
        sa.CheckConstraint(
            "period_end >= period_start", name=op.f("ck_construction_certificates_period_order")
        ),
        sa.CheckConstraint(
            "retention_release_amount >= 0",
            name=op.f("ck_construction_certificates_release_nonneg"),
        ),
        sa.CheckConstraint("tax_amount >= 0", name=op.f("ck_construction_certificates_tax_nonneg")),
        sa.ForeignKeyConstraint(
            ["certified_by_user_id"],
            ["users.id"],
            name=op.f("fk_construction_certificates_certified_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["contract_id", "project_id"],
            ["construction_contracts.id", "construction_contracts.project_id"],
            name="contract",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_construction_certificates_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_construction_certificates_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["rejected_by_user_id"],
            ["users.id"],
            name=op.f("fk_construction_certificates_rejected_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reversed_by_user_id"],
            ["users.id"],
            name=op.f("fk_construction_certificates_reversed_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["submitted_by_user_id"],
            ["users.id"],
            name=op.f("fk_construction_certificates_submitted_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_construction_certificates")),
        sa.UniqueConstraint("contract_id", "certificate_number", name="uq_cx_cert_number"),
        sa.UniqueConstraint("id", "contract_id", "project_id", name="cx_cert_contract_project"),
        sa.UniqueConstraint("id", "project_id", name="cx_cert_project"),
    )
    op.create_index(
        op.f("ix_construction_certificates_project_id"),
        "construction_certificates",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_cx_certs_certified_at", "construction_certificates", ["certified_at"], unique=False
    )
    op.create_index(
        "ix_cx_certs_contract_status",
        "construction_certificates",
        ["contract_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_cx_certs_project_status",
        "construction_certificates",
        ["project_id", "status"],
        unique=False,
    )
    op.create_table(
        "construction_forecast_versions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("currency_id", sa.UUID(), nullable=False),
        sa.Column("budget_version_id", sa.UUID(), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("source_version_id", sa.UUID(), nullable=True),
        sa.Column("change_reason", sa.String(length=1000), nullable=False),
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
            "status IN ('draft', 'submitted', 'approved', 'active', 'superseded', 'rejected')",
            name=op.f("ck_construction_forecast_versions_status_ok"),
        ),
        sa.CheckConstraint(
            "length(change_reason) > 0",
            name=op.f("ck_construction_forecast_versions_reason_present"),
        ),
        sa.CheckConstraint(
            "version_number >= 1", name=op.f("ck_construction_forecast_versions_number_positive")
        ),
        sa.ForeignKeyConstraint(
            ["activated_by_user_id"],
            ["users.id"],
            name=op.f("fk_construction_forecast_versions_activated_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["approved_by_user_id"],
            ["users.id"],
            name=op.f("fk_construction_forecast_versions_approved_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["budget_version_id", "project_id"],
            ["construction_budget_versions.id", "construction_budget_versions.project_id"],
            name="budget",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_construction_forecast_versions_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["currency_id"],
            ["currencies.id"],
            name=op.f("fk_construction_forecast_versions_currency_id_currencies"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_construction_forecast_versions_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["rejected_by_user_id"],
            ["users.id"],
            name=op.f("fk_construction_forecast_versions_rejected_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["submitted_by_user_id"],
            ["users.id"],
            name=op.f("fk_construction_forecast_versions_submitted_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_construction_forecast_versions")),
        sa.UniqueConstraint("id", "project_id", name="cx_forecast_project"),
        sa.UniqueConstraint("project_id", "version_number", name="uq_cx_forecast_number"),
    )
    op.create_index(
        op.f("ix_construction_forecast_versions_project_id"),
        "construction_forecast_versions",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_cx_forecasts_project_status",
        "construction_forecast_versions",
        ["project_id", "status"],
        unique=False,
    )
    op.create_index(
        "uq_cx_forecasts_one_active",
        "construction_forecast_versions",
        ["project_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_index(
        "uq_cx_forecasts_one_open",
        "construction_forecast_versions",
        ["project_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('draft', 'submitted', 'approved')"),
    )
    op.create_table(
        "construction_payments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("contract_id", sa.UUID(), nullable=False),
        sa.Column("payment_reference", sa.String(length=64), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("value_date", sa.Date(), nullable=True),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("currency_id", sa.UUID(), nullable=False),
        sa.Column("bank_reference", sa.String(length=200), nullable=True),
        sa.Column("proof_reference", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("notes", sa.String(length=2000), nullable=True),
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
        sa.Column("recorded_by_user_id", sa.UUID(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_by_user_id", sa.UUID(), nullable=True),
        sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reversed_by_user_id", sa.UUID(), nullable=True),
        sa.Column("reversal_reason", sa.String(length=1000), nullable=True),
        sa.CheckConstraint(
            "status <> 'reversed' OR reversal_reason IS NOT NULL",
            name=op.f("ck_construction_payments_reversed_has_reason"),
        ),
        sa.CheckConstraint(
            "status IN ('recorded', 'confirmed', 'reversed')",
            name=op.f("ck_construction_payments_status_ok"),
        ),
        sa.CheckConstraint("amount > 0", name=op.f("ck_construction_payments_amount_positive")),
        sa.CheckConstraint(
            "length(payment_reference) > 0", name=op.f("ck_construction_payments_reference_present")
        ),
        sa.CheckConstraint(
            "value_date IS NULL OR value_date >= payment_date",
            name=op.f("ck_construction_payments_value_order"),
        ),
        sa.ForeignKeyConstraint(
            ["confirmed_by_user_id"],
            ["users.id"],
            name=op.f("fk_construction_payments_confirmed_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["contract_id", "project_id"],
            ["construction_contracts.id", "construction_contracts.project_id"],
            name="contract",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["currency_id"],
            ["currencies.id"],
            name=op.f("fk_construction_payments_currency_id_currencies"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_construction_payments_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["recorded_by_user_id"],
            ["users.id"],
            name=op.f("fk_construction_payments_recorded_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reversed_by_user_id"],
            ["users.id"],
            name=op.f("fk_construction_payments_reversed_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_construction_payments")),
        sa.UniqueConstraint("id", "contract_id", "project_id", name="cx_payment_contract_project"),
        sa.UniqueConstraint("id", "project_id", name="cx_payment_project"),
        sa.UniqueConstraint("project_id", "payment_reference", name="uq_cx_payment_reference"),
    )
    op.create_index(
        op.f("ix_construction_payments_project_id"),
        "construction_payments",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_cx_payments_contract_status",
        "construction_payments",
        ["contract_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_cx_payments_payment_date", "construction_payments", ["payment_date"], unique=False
    )
    op.create_index(
        "ix_cx_payments_project_status",
        "construction_payments",
        ["project_id", "status"],
        unique=False,
    )
    op.create_table(
        "construction_variations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("contract_id", sa.UUID(), nullable=False),
        sa.Column("variation_number", sa.String(length=64), nullable=False),
        sa.Column("instruction_reference", sa.String(length=200), nullable=True),
        sa.Column("description", sa.String(length=1000), nullable=False),
        sa.Column("cause", sa.String(length=1000), nullable=True),
        sa.Column("requested_date", sa.Date(), nullable=False),
        sa.Column("time_impact_days", sa.Integer(), nullable=False),
        sa.Column("funding_source", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
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
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_by_user_id", sa.UUID(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_user_id", sa.UUID(), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_by_user_id", sa.UUID(), nullable=True),
        sa.Column("rejection_reason", sa.String(length=1000), nullable=True),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("withdrawal_reason", sa.String(length=1000), nullable=True),
        sa.CheckConstraint(
            "status <> 'rejected' OR rejection_reason IS NOT NULL",
            name=op.f("ck_construction_variations_rejected_has_reason"),
        ),
        sa.CheckConstraint(
            "status <> 'withdrawn' OR withdrawal_reason IS NOT NULL",
            name=op.f("ck_construction_variations_withdrawn_has_reason"),
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'submitted', 'approved', 'rejected', 'withdrawn')",
            name=op.f("ck_construction_variations_status_ok"),
        ),
        sa.CheckConstraint(
            "length(description) > 0", name=op.f("ck_construction_variations_description_present")
        ),
        sa.CheckConstraint(
            "length(variation_number) > 0", name=op.f("ck_construction_variations_number_present")
        ),
        sa.ForeignKeyConstraint(
            ["approved_by_user_id"],
            ["users.id"],
            name=op.f("fk_construction_variations_approved_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["contract_id", "project_id"],
            ["construction_contracts.id", "construction_contracts.project_id"],
            name="contract",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_construction_variations_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_construction_variations_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["rejected_by_user_id"],
            ["users.id"],
            name=op.f("fk_construction_variations_rejected_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["submitted_by_user_id"],
            ["users.id"],
            name=op.f("fk_construction_variations_submitted_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_construction_variations")),
        sa.UniqueConstraint("contract_id", "variation_number", name="uq_cx_variation_number"),
        sa.UniqueConstraint("id", "project_id", name="cx_variation_project"),
    )
    op.create_index(
        op.f("ix_construction_variations_project_id"),
        "construction_variations",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_cx_variations_contract_status",
        "construction_variations",
        ["contract_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_cx_variations_project_status",
        "construction_variations",
        ["project_id", "status"],
        unique=False,
    )
    op.create_table(
        "construction_cost_codes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("parent_cost_code_id", sa.UUID(), nullable=True),
        sa.Column("cost_category", sa.String(length=16), nullable=False),
        sa.Column("package", sa.String(length=120), nullable=True),
        sa.Column("phase_id", sa.UUID(), nullable=True),
        sa.Column("building_id", sa.UUID(), nullable=True),
        sa.Column("notes", sa.String(length=2000), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
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
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "cost_category IN ('hard', 'soft', 'contingency', 'other')",
            name=op.f("ck_construction_cost_codes_category_ok"),
        ),
        sa.CheckConstraint(
            "length(code) > 0", name=op.f("ck_construction_cost_codes_code_present")
        ),
        sa.CheckConstraint(
            "length(name) > 0", name=op.f("ck_construction_cost_codes_name_present")
        ),
        sa.CheckConstraint(
            "parent_cost_code_id <> id", name=op.f("ck_construction_cost_codes_parent_not_self")
        ),
        sa.ForeignKeyConstraint(
            ["building_id", "project_id"],
            ["buildings.id", "buildings.project_id"],
            name="building",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_construction_cost_codes_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["parent_cost_code_id", "project_id"],
            ["construction_cost_codes.id", "construction_cost_codes.project_id"],
            name="parent_code",
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
            name=op.f("fk_construction_cost_codes_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_construction_cost_codes")),
        sa.UniqueConstraint("id", "project_id", name="cx_cost_code_project"),
        sa.UniqueConstraint("project_id", "code", name="uq_cx_cost_code"),
    )
    op.create_index(
        op.f("ix_construction_cost_codes_project_id"),
        "construction_cost_codes",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_cx_cost_codes_project_active",
        "construction_cost_codes",
        ["project_id", "is_active"],
        unique=False,
    )
    op.create_table(
        "construction_invoices",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("contract_id", sa.UUID(), nullable=False),
        sa.Column("certificate_id", sa.UUID(), nullable=True),
        sa.Column("invoice_number", sa.String(length=64), nullable=False),
        sa.Column("invoice_type", sa.String(length=24), nullable=False),
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("amount_ex_tax", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("tax_amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("accounting_reference", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("dispute_reason", sa.String(length=1000), nullable=True),
        sa.Column("notes", sa.String(length=2000), nullable=True),
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
        sa.Column("recorded_by_user_id", sa.UUID(), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_user_id", sa.UUID(), nullable=True),
        sa.Column("disputed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("disputed_by_user_id", sa.UUID(), nullable=True),
        sa.Column("dispute_resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dispute_resolution_reason", sa.String(length=1000), nullable=True),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("voided_by_user_id", sa.UUID(), nullable=True),
        sa.Column("void_reason", sa.String(length=1000), nullable=True),
        sa.CheckConstraint(
            "invoice_type <> 'advance' OR certificate_id IS NULL",
            name=op.f("ck_construction_invoices_advance_has_no_certificate"),
        ),
        sa.CheckConstraint(
            "invoice_type = 'advance' OR invoice_type = 'other' OR certificate_id IS NOT NULL",
            name=op.f("ck_construction_invoices_claim_has_certificate"),
        ),
        sa.CheckConstraint(
            "invoice_type IN ('advance', 'progress', 'retention_release', 'final', 'other')",
            name=op.f("ck_construction_invoices_type_ok"),
        ),
        sa.CheckConstraint(
            "status <> 'disputed' OR dispute_reason IS NOT NULL",
            name=op.f("ck_construction_invoices_disputed_has_reason"),
        ),
        sa.CheckConstraint(
            "status <> 'voided' OR void_reason IS NOT NULL",
            name=op.f("ck_construction_invoices_voided_has_reason"),
        ),
        sa.CheckConstraint(
            "status IN ('recorded', 'approved', 'disputed', 'voided')",
            name=op.f("ck_construction_invoices_status_ok"),
        ),
        sa.CheckConstraint(
            "amount_ex_tax >= 0", name=op.f("ck_construction_invoices_amount_nonneg")
        ),
        sa.CheckConstraint(
            "due_date IS NULL OR due_date >= invoice_date",
            name=op.f("ck_construction_invoices_due_order"),
        ),
        sa.CheckConstraint(
            "length(invoice_number) > 0", name=op.f("ck_construction_invoices_number_present")
        ),
        sa.CheckConstraint("tax_amount >= 0", name=op.f("ck_construction_invoices_tax_nonneg")),
        sa.ForeignKeyConstraint(
            ["approved_by_user_id"],
            ["users.id"],
            name=op.f("fk_construction_invoices_approved_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["certificate_id", "contract_id", "project_id"],
            [
                "construction_certificates.id",
                "construction_certificates.contract_id",
                "construction_certificates.project_id",
            ],
            name="certificate",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["contract_id", "project_id"],
            ["construction_contracts.id", "construction_contracts.project_id"],
            name="contract",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["disputed_by_user_id"],
            ["users.id"],
            name=op.f("fk_construction_invoices_disputed_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_construction_invoices_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["recorded_by_user_id"],
            ["users.id"],
            name=op.f("fk_construction_invoices_recorded_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["voided_by_user_id"],
            ["users.id"],
            name=op.f("fk_construction_invoices_voided_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_construction_invoices")),
        sa.UniqueConstraint("contract_id", "invoice_number", name="uq_cx_invoice_number"),
        sa.UniqueConstraint("id", "contract_id", "project_id", name="cx_invoice_contract_project"),
        sa.UniqueConstraint("id", "project_id", name="cx_invoice_project"),
    )
    op.create_index(
        op.f("ix_construction_invoices_project_id"),
        "construction_invoices",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_cx_invoices_certificate", "construction_invoices", ["certificate_id"], unique=False
    )
    op.create_index(
        "ix_cx_invoices_contract_status",
        "construction_invoices",
        ["contract_id", "status"],
        unique=False,
    )
    op.create_index("ix_cx_invoices_due_date", "construction_invoices", ["due_date"], unique=False)
    op.create_index(
        "ix_cx_invoices_project_status",
        "construction_invoices",
        ["project_id", "status"],
        unique=False,
    )
    op.create_table(
        "construction_milestones",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("milestone_type", sa.String(length=16), nullable=False),
        sa.Column("phase_id", sa.UUID(), nullable=True),
        sa.Column("building_id", sa.UUID(), nullable=True),
        sa.Column("planned_date", sa.Date(), nullable=True),
        sa.Column("forecast_date", sa.Date(), nullable=True),
        sa.Column("actual_achieved_date", sa.Date(), nullable=True),
        sa.Column("certified_date", sa.Date(), nullable=True),
        sa.Column("progress_fraction", sa.Numeric(precision=9, scale=6), nullable=False),
        sa.Column("evidence_reference", sa.String(length=500), nullable=True),
        sa.Column("linked_certificate_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("notes", sa.String(length=2000), nullable=True),
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
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.Column("achieved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("achieved_by_user_id", sa.UUID(), nullable=True),
        sa.Column("certified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("certified_by_user_id", sa.UUID(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_reason", sa.String(length=1000), nullable=True),
        sa.CheckConstraint(
            "(status = 'certified') = (certified_date IS NOT NULL)",
            name=op.f("ck_construction_milestones_certified_shape"),
        ),
        sa.CheckConstraint(
            "milestone_type IN ('start', 'progress', 'completion', 'other')",
            name=op.f("ck_construction_milestones_type_ok"),
        ),
        sa.CheckConstraint(
            "status <> 'cancelled' OR cancellation_reason IS NOT NULL",
            name=op.f("ck_construction_milestones_cancelled_has_reason"),
        ),
        sa.CheckConstraint(
            "status IN ('planned', 'in_progress', 'achieved', 'certified', 'cancelled')",
            name=op.f("ck_construction_milestones_status_ok"),
        ),
        sa.CheckConstraint(
            "building_id IS NULL OR phase_id IS NULL OR building_id IS NOT NULL",
            name=op.f("ck_construction_milestones_scope_shape"),
        ),
        sa.CheckConstraint(
            "length(code) > 0", name=op.f("ck_construction_milestones_code_present")
        ),
        sa.CheckConstraint(
            "length(name) > 0", name=op.f("ck_construction_milestones_name_present")
        ),
        sa.CheckConstraint(
            "progress_fraction >= 0 AND progress_fraction <= 1",
            name=op.f("ck_construction_milestones_progress_range"),
        ),
        sa.ForeignKeyConstraint(
            ["achieved_by_user_id"],
            ["users.id"],
            name=op.f("fk_construction_milestones_achieved_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["building_id", "project_id"],
            ["buildings.id", "buildings.project_id"],
            name="building",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["certified_by_user_id"],
            ["users.id"],
            name=op.f("fk_construction_milestones_certified_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_construction_milestones_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["linked_certificate_id", "project_id"],
            ["construction_certificates.id", "construction_certificates.project_id"],
            name="certificate",
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
            name=op.f("fk_construction_milestones_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_construction_milestones")),
        sa.UniqueConstraint("id", "project_id", name="cx_milestone_project"),
        sa.UniqueConstraint("project_id", "code", name="uq_cx_milestone_code"),
    )
    op.create_index(
        op.f("ix_construction_milestones_project_id"),
        "construction_milestones",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_cx_milestones_building", "construction_milestones", ["building_id"], unique=False
    )
    op.create_index("ix_cx_milestones_phase", "construction_milestones", ["phase_id"], unique=False)
    op.create_index(
        "ix_cx_milestones_planned_date", "construction_milestones", ["planned_date"], unique=False
    )
    op.create_index(
        "ix_cx_milestones_project_status",
        "construction_milestones",
        ["project_id", "status"],
        unique=False,
    )
    op.create_table(
        "construction_budget_lines",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("budget_version_id", sa.UUID(), nullable=False),
        sa.Column("cost_code_id", sa.UUID(), nullable=False),
        sa.Column("baseline_amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("approved_budget_amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("contingency_amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("funding_source", sa.String(length=120), nullable=True),
        sa.Column("notes", sa.String(length=2000), nullable=True),
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
            "approved_budget_amount >= 0", name=op.f("ck_construction_budget_lines_approved_nonneg")
        ),
        sa.CheckConstraint(
            "baseline_amount >= 0", name=op.f("ck_construction_budget_lines_baseline_nonneg")
        ),
        sa.CheckConstraint(
            "contingency_amount >= 0", name=op.f("ck_construction_budget_lines_contingency_nonneg")
        ),
        sa.ForeignKeyConstraint(
            ["budget_version_id", "project_id"],
            ["construction_budget_versions.id", "construction_budget_versions.project_id"],
            name="budget",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["cost_code_id", "project_id"],
            ["construction_cost_codes.id", "construction_cost_codes.project_id"],
            name="cost_code",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_construction_budget_lines")),
        sa.UniqueConstraint("budget_version_id", "cost_code_id", name="uq_cx_budget_line"),
    )
    op.create_index(
        "ix_cx_budget_lines_version",
        "construction_budget_lines",
        ["budget_version_id"],
        unique=False,
    )
    op.create_table(
        "construction_certificate_lines",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("certificate_id", sa.UUID(), nullable=False),
        sa.Column("cost_code_id", sa.UUID(), nullable=False),
        sa.Column("current_work_value_ex_tax", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("notes", sa.String(length=2000), nullable=True),
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
            "current_work_value_ex_tax >= 0",
            name=op.f("ck_construction_certificate_lines_work_nonneg"),
        ),
        sa.ForeignKeyConstraint(
            ["certificate_id", "project_id"],
            ["construction_certificates.id", "construction_certificates.project_id"],
            name="certificate",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["cost_code_id", "project_id"],
            ["construction_cost_codes.id", "construction_cost_codes.project_id"],
            name="cost_code",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_construction_certificate_lines")),
        sa.UniqueConstraint("certificate_id", "cost_code_id", name="uq_cx_cert_line"),
    )
    op.create_index(
        "ix_cx_cert_lines_certificate",
        "construction_certificate_lines",
        ["certificate_id"],
        unique=False,
    )
    op.create_index(
        "ix_cx_cert_lines_cost_code",
        "construction_certificate_lines",
        ["cost_code_id"],
        unique=False,
    )
    op.create_table(
        "construction_contract_lines",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("contract_id", sa.UUID(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("cost_code_id", sa.UUID(), nullable=False),
        sa.Column("original_amount_ex_tax", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("notes", sa.String(length=2000), nullable=True),
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
            "length(description) > 0",
            name=op.f("ck_construction_contract_lines_description_present"),
        ),
        sa.CheckConstraint(
            "original_amount_ex_tax >= 0", name=op.f("ck_construction_contract_lines_amount_nonneg")
        ),
        sa.CheckConstraint(
            "sequence >= 1", name=op.f("ck_construction_contract_lines_sequence_positive")
        ),
        sa.ForeignKeyConstraint(
            ["contract_id", "project_id"],
            ["construction_contracts.id", "construction_contracts.project_id"],
            name="contract",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["cost_code_id", "project_id"],
            ["construction_cost_codes.id", "construction_cost_codes.project_id"],
            name="cost_code",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_construction_contract_lines")),
        sa.UniqueConstraint("contract_id", "sequence", name="uq_cx_contract_line_seq"),
    )
    op.create_index(
        "ix_cx_contract_lines_contract",
        "construction_contract_lines",
        ["contract_id"],
        unique=False,
    )
    op.create_index(
        "ix_cx_contract_lines_cost_code",
        "construction_contract_lines",
        ["cost_code_id"],
        unique=False,
    )
    op.create_table(
        "construction_forecast_lines",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("forecast_version_id", sa.UUID(), nullable=False),
        sa.Column("cost_code_id", sa.UUID(), nullable=False),
        sa.Column(
            "forecast_remaining_amount_ex_tax", sa.Numeric(precision=18, scale=2), nullable=False
        ),
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
            "forecast_remaining_amount_ex_tax >= 0",
            name=op.f("ck_construction_forecast_lines_remaining_nonneg"),
        ),
        sa.ForeignKeyConstraint(
            ["cost_code_id", "project_id"],
            ["construction_cost_codes.id", "construction_cost_codes.project_id"],
            name="cost_code",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["forecast_version_id", "project_id"],
            ["construction_forecast_versions.id", "construction_forecast_versions.project_id"],
            name="forecast",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_construction_forecast_lines")),
        sa.UniqueConstraint("forecast_version_id", "cost_code_id", name="uq_cx_forecast_line"),
    )
    op.create_index(
        "ix_cx_forecast_lines_version",
        "construction_forecast_lines",
        ["forecast_version_id"],
        unique=False,
    )
    op.create_table(
        "construction_milestone_dependencies",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("milestone_id", sa.UUID(), nullable=False),
        sa.Column("depends_on_milestone_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "milestone_id <> depends_on_milestone_id",
            name=op.f("ck_construction_milestone_dependencies_not_self"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_construction_milestone_dependencies_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["depends_on_milestone_id", "project_id"],
            ["construction_milestones.id", "construction_milestones.project_id"],
            name="depends_on",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["milestone_id", "project_id"],
            ["construction_milestones.id", "construction_milestones.project_id"],
            name="milestone",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_construction_milestone_dependencies")),
        sa.UniqueConstraint("milestone_id", "depends_on_milestone_id", name="uq_cx_dep_pair"),
    )
    op.create_index(
        "ix_cx_deps_depends_on",
        "construction_milestone_dependencies",
        ["depends_on_milestone_id"],
        unique=False,
    )
    op.create_index(
        "ix_cx_deps_milestone",
        "construction_milestone_dependencies",
        ["milestone_id"],
        unique=False,
    )
    op.create_table(
        "construction_payment_allocations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("contract_id", sa.UUID(), nullable=False),
        sa.Column("payment_id", sa.UUID(), nullable=False),
        sa.Column("invoice_id", sa.UUID(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
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
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "amount > 0", name=op.f("ck_construction_payment_allocations_amount_positive")
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_construction_payment_allocations_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["invoice_id", "contract_id", "project_id"],
            [
                "construction_invoices.id",
                "construction_invoices.contract_id",
                "construction_invoices.project_id",
            ],
            name="invoice",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["payment_id", "contract_id", "project_id"],
            [
                "construction_payments.id",
                "construction_payments.contract_id",
                "construction_payments.project_id",
            ],
            name="payment",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_construction_payment_allocations")),
        sa.UniqueConstraint("payment_id", "invoice_id", name="uq_cx_alloc_pair"),
    )
    op.create_index(
        "ix_cx_allocs_invoice", "construction_payment_allocations", ["invoice_id"], unique=False
    )
    op.create_index(
        "ix_cx_allocs_payment", "construction_payment_allocations", ["payment_id"], unique=False
    )
    op.create_table(
        "construction_variation_lines",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("variation_id", sa.UUID(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("cost_code_id", sa.UUID(), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("value_delta_ex_tax", sa.Numeric(precision=18, scale=2), nullable=False),
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
            "length(description) > 0",
            name=op.f("ck_construction_variation_lines_description_present"),
        ),
        sa.CheckConstraint(
            "sequence >= 1", name=op.f("ck_construction_variation_lines_sequence_positive")
        ),
        sa.CheckConstraint(
            "value_delta_ex_tax <> 0", name=op.f("ck_construction_variation_lines_delta_nonzero")
        ),
        sa.ForeignKeyConstraint(
            ["cost_code_id", "project_id"],
            ["construction_cost_codes.id", "construction_cost_codes.project_id"],
            name="cost_code",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["variation_id", "project_id"],
            ["construction_variations.id", "construction_variations.project_id"],
            name="variation",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_construction_variation_lines")),
        sa.UniqueConstraint("variation_id", "sequence", name="uq_cx_variation_line_seq"),
    )
    op.create_index(
        "ix_cx_variation_lines_cost_code",
        "construction_variation_lines",
        ["cost_code_id"],
        unique=False,
    )
    op.create_index(
        "ix_cx_variation_lines_variation",
        "construction_variation_lines",
        ["variation_id"],
        unique=False,
    )
    op.add_column(
        "unit_economics_cost_pools",
        sa.Column("source_construction_forecast_version_id", sa.UUID(), nullable=True),
    )
    op.create_index(
        "uq_ue_pools_one_construction",
        "unit_economics_cost_pools",
        ["allocation_version_id"],
        unique=True,
        postgresql_where=sa.text("source_kind = 'construction_forecast'"),
    )
    op.create_foreign_key(
        "construction_forecast",
        "unit_economics_cost_pools",
        "construction_forecast_versions",
        ["source_construction_forecast_version_id", "project_id"],
        ["id", "project_id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        op.f("ck_unit_economics_cost_pools_cx_provenance_shape"),
        "unit_economics_cost_pools",
        "(source_kind = 'construction_forecast')"
        " = (source_construction_forecast_version_id IS NOT NULL)",
    )
    op.create_check_constraint(
        op.f("ck_unit_economics_cost_pools_cx_source_shape"),
        "unit_economics_cost_pools",
        "source_kind <> 'construction_forecast' OR (category = 'hard' AND scope_kind = 'project')",
    )


def downgrade() -> None:
    """Revert this revision."""
    op.drop_constraint(
        op.f("ck_unit_economics_cost_pools_cx_source_shape"),
        "unit_economics_cost_pools",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_unit_economics_cost_pools_cx_provenance_shape"),
        "unit_economics_cost_pools",
        type_="check",
    )
    op.drop_constraint("construction_forecast", "unit_economics_cost_pools", type_="foreignkey")
    op.drop_index(
        "uq_ue_pools_one_construction",
        table_name="unit_economics_cost_pools",
        postgresql_where=sa.text("source_kind = 'construction_forecast'"),
    )
    op.drop_column("unit_economics_cost_pools", "source_construction_forecast_version_id")
    op.drop_index("ix_cx_variation_lines_variation", table_name="construction_variation_lines")
    op.drop_index("ix_cx_variation_lines_cost_code", table_name="construction_variation_lines")
    op.drop_table("construction_variation_lines")
    op.drop_index("ix_cx_allocs_payment", table_name="construction_payment_allocations")
    op.drop_index("ix_cx_allocs_invoice", table_name="construction_payment_allocations")
    op.drop_table("construction_payment_allocations")
    op.drop_index("ix_cx_deps_milestone", table_name="construction_milestone_dependencies")
    op.drop_index("ix_cx_deps_depends_on", table_name="construction_milestone_dependencies")
    op.drop_table("construction_milestone_dependencies")
    op.drop_index("ix_cx_forecast_lines_version", table_name="construction_forecast_lines")
    op.drop_table("construction_forecast_lines")
    op.drop_index("ix_cx_contract_lines_cost_code", table_name="construction_contract_lines")
    op.drop_index("ix_cx_contract_lines_contract", table_name="construction_contract_lines")
    op.drop_table("construction_contract_lines")
    op.drop_index("ix_cx_cert_lines_cost_code", table_name="construction_certificate_lines")
    op.drop_index("ix_cx_cert_lines_certificate", table_name="construction_certificate_lines")
    op.drop_table("construction_certificate_lines")
    op.drop_index("ix_cx_budget_lines_version", table_name="construction_budget_lines")
    op.drop_table("construction_budget_lines")
    op.drop_index("ix_cx_milestones_project_status", table_name="construction_milestones")
    op.drop_index("ix_cx_milestones_planned_date", table_name="construction_milestones")
    op.drop_index("ix_cx_milestones_phase", table_name="construction_milestones")
    op.drop_index("ix_cx_milestones_building", table_name="construction_milestones")
    op.drop_index(
        op.f("ix_construction_milestones_project_id"), table_name="construction_milestones"
    )
    op.drop_table("construction_milestones")
    op.drop_index("ix_cx_invoices_project_status", table_name="construction_invoices")
    op.drop_index("ix_cx_invoices_due_date", table_name="construction_invoices")
    op.drop_index("ix_cx_invoices_contract_status", table_name="construction_invoices")
    op.drop_index("ix_cx_invoices_certificate", table_name="construction_invoices")
    op.drop_index(op.f("ix_construction_invoices_project_id"), table_name="construction_invoices")
    op.drop_table("construction_invoices")
    op.drop_index("ix_cx_cost_codes_project_active", table_name="construction_cost_codes")
    op.drop_index(
        op.f("ix_construction_cost_codes_project_id"), table_name="construction_cost_codes"
    )
    op.drop_table("construction_cost_codes")
    op.drop_index("ix_cx_variations_project_status", table_name="construction_variations")
    op.drop_index("ix_cx_variations_contract_status", table_name="construction_variations")
    op.drop_index(
        op.f("ix_construction_variations_project_id"), table_name="construction_variations"
    )
    op.drop_table("construction_variations")
    op.drop_index("ix_cx_payments_project_status", table_name="construction_payments")
    op.drop_index("ix_cx_payments_payment_date", table_name="construction_payments")
    op.drop_index("ix_cx_payments_contract_status", table_name="construction_payments")
    op.drop_index(op.f("ix_construction_payments_project_id"), table_name="construction_payments")
    op.drop_table("construction_payments")
    op.drop_index(
        "uq_cx_forecasts_one_open",
        table_name="construction_forecast_versions",
        postgresql_where=sa.text("status IN ('draft', 'submitted', 'approved')"),
    )
    op.drop_index(
        "uq_cx_forecasts_one_active",
        table_name="construction_forecast_versions",
        postgresql_where=sa.text("status = 'active'"),
    )
    op.drop_index("ix_cx_forecasts_project_status", table_name="construction_forecast_versions")
    op.drop_index(
        op.f("ix_construction_forecast_versions_project_id"),
        table_name="construction_forecast_versions",
    )
    op.drop_table("construction_forecast_versions")
    op.drop_index("ix_cx_certs_project_status", table_name="construction_certificates")
    op.drop_index("ix_cx_certs_contract_status", table_name="construction_certificates")
    op.drop_index("ix_cx_certs_certified_at", table_name="construction_certificates")
    op.drop_index(
        op.f("ix_construction_certificates_project_id"), table_name="construction_certificates"
    )
    op.drop_table("construction_certificates")
    op.drop_index("ix_cx_contracts_project_status", table_name="construction_contracts")
    op.drop_index(op.f("ix_construction_contracts_project_id"), table_name="construction_contracts")
    op.drop_table("construction_contracts")
    op.drop_index(
        "uq_cx_budgets_one_open",
        table_name="construction_budget_versions",
        postgresql_where=sa.text("status IN ('draft', 'submitted', 'approved')"),
    )
    op.drop_index(
        "uq_cx_budgets_one_active",
        table_name="construction_budget_versions",
        postgresql_where=sa.text("status = 'active'"),
    )
    op.drop_index("ix_cx_budgets_project_status", table_name="construction_budget_versions")
    op.drop_index(
        op.f("ix_construction_budget_versions_project_id"),
        table_name="construction_budget_versions",
    )
    op.drop_table("construction_budget_versions")
