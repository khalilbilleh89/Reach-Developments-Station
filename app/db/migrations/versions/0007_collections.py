"""Collections: receipts, allocations, actions, disputes, waivers, restructures, refunds.

Seven new tables and exactly one column on an existing one. Nothing in
``payment_plan_installments``, ``sale_contracts`` or ``sale_cancellations`` is
altered: what the buyer owes stays PR-MVP-06's, the contract stays PR-MVP-05's,
and this revision only adds the ledger that records what actually arrived.

The single column, ``payment_plans.collections_started_at``, is the boundary
marker. It goes on the plan rather than in a collections table because the rule
it guards is one payment plans enforces: once cash has been confirmed against a
schedule, the ordinary activation path must refuse to swap the instalments out
from underneath the allocations pointing at them.

``collection_restructures`` is created before ``collection_receipt_allocations``
because a superseded allocation points back at the restructure that superseded
it. The downgrade drops all seven in the reverse order and removes the column,
leaving payment plans, sales and inventory exactly as 0006 left them.

Revision ID: 0007_collections
Revises: 0006_payment_plans
Create Date: 2026-08-31 15:30:48.355193+00:00

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_collections"
down_revision: str | Sequence[str] | None = "0006_payment_plans"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply this revision."""
    op.create_table(
        "collection_receipts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("sale_contract_id", sa.UUID(), nullable=False),
        sa.Column("receipt_number", sa.String(length=32), nullable=False),
        sa.Column("currency_id", sa.UUID(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("receipt_date", sa.Date(), nullable=False),
        sa.Column("bank_reference", sa.String(length=200), nullable=True),
        sa.Column("external_reference", sa.String(length=200), nullable=True),
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
        sa.Column("reversal_reason", sa.String(length=500), nullable=True),
        sa.CheckConstraint(
            "status <> 'confirmed' OR (confirmed_at IS NOT NULL AND confirmed_by_user_id IS "
            "NOT NULL)",
            name=op.f("ck_collection_receipts_confirmed_has_actor"),
        ),
        sa.CheckConstraint(
            "status <> 'reversed' OR (reversed_at IS NOT NULL AND reversed_by_user_id IS NOT "
            "NULL AND reversal_reason IS NOT NULL)",
            name=op.f("ck_collection_receipts_reversed_has_reason"),
        ),
        sa.CheckConstraint(
            "status IN ('recorded', 'confirmed', 'reversed')",
            name=op.f("ck_collection_receipts_status_ok"),
        ),
        sa.CheckConstraint("amount > 0", name=op.f("ck_collection_receipts_amount_positive")),
        sa.ForeignKeyConstraint(
            ["confirmed_by_user_id"],
            ["users.id"],
            name=op.f("fk_collection_receipts_confirmed_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["currency_id"],
            ["currencies.id"],
            name=op.f("fk_collection_receipts_currency_id_currencies"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_collection_receipts_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["recorded_by_user_id"],
            ["users.id"],
            name=op.f("fk_collection_receipts_recorded_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reversed_by_user_id"],
            ["users.id"],
            name=op.f("fk_collection_receipts_reversed_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["sale_contract_id", "project_id"],
            ["sale_contracts.id", "sale_contracts.project_id"],
            name="sale",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_collection_receipts")),
        sa.UniqueConstraint("id", "project_id", name="collection_receipt_project"),
        sa.UniqueConstraint("project_id", "receipt_number", name="uq_collection_receipts_number"),
    )
    op.create_index(
        "ix_collection_receipts_project_id", "collection_receipts", ["project_id"], unique=False
    )
    op.create_index(
        "ix_collection_receipts_receipt_date", "collection_receipts", ["receipt_date"], unique=False
    )
    op.create_index(
        "ix_collection_receipts_sale_status",
        "collection_receipts",
        ["sale_contract_id", "status"],
        unique=False,
    )
    op.create_table(
        "collection_refunds",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("sale_contract_id", sa.UUID(), nullable=False),
        sa.Column("cancellation_id", sa.UUID(), nullable=False),
        sa.Column("refund_number", sa.String(length=32), nullable=False),
        sa.Column("currency_id", sa.UUID(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("refund_date", sa.Date(), nullable=False),
        sa.Column("bank_reference", sa.String(length=200), nullable=True),
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
        sa.Column("reversal_reason", sa.String(length=500), nullable=True),
        sa.CheckConstraint(
            "status <> 'confirmed' OR (confirmed_at IS NOT NULL AND confirmed_by_user_id IS "
            "NOT NULL)",
            name=op.f("ck_collection_refunds_confirmed_has_actor"),
        ),
        sa.CheckConstraint(
            "status <> 'reversed' OR (reversed_at IS NOT NULL AND reversed_by_user_id IS NOT "
            "NULL AND reversal_reason IS NOT NULL)",
            name=op.f("ck_collection_refunds_reversed_has_reason"),
        ),
        sa.CheckConstraint(
            "status IN ('recorded', 'confirmed', 'reversed')",
            name=op.f("ck_collection_refunds_status_ok"),
        ),
        sa.CheckConstraint("amount > 0", name=op.f("ck_collection_refunds_amount_positive")),
        sa.ForeignKeyConstraint(
            ["cancellation_id", "project_id"],
            ["sale_cancellations.id", "sale_cancellations.project_id"],
            name="cancellation",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["confirmed_by_user_id"],
            ["users.id"],
            name=op.f("fk_collection_refunds_confirmed_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["currency_id"],
            ["currencies.id"],
            name=op.f("fk_collection_refunds_currency_id_currencies"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["recorded_by_user_id"],
            ["users.id"],
            name=op.f("fk_collection_refunds_recorded_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reversed_by_user_id"],
            ["users.id"],
            name=op.f("fk_collection_refunds_reversed_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["sale_contract_id", "project_id"],
            ["sale_contracts.id", "sale_contracts.project_id"],
            name="sale",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_collection_refunds")),
        sa.UniqueConstraint("id", "project_id", name="collection_refund_project"),
        sa.UniqueConstraint("project_id", "refund_number", name="uq_collection_refunds_number"),
    )
    op.create_index(
        "ix_collection_refunds_cancellation",
        "collection_refunds",
        ["cancellation_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_collection_refunds_project_id", "collection_refunds", ["project_id"], unique=False
    )
    op.create_index(
        "ix_collection_refunds_sale_status",
        "collection_refunds",
        ["sale_contract_id", "status"],
        unique=False,
    )
    op.create_table(
        "collection_restructures",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("sale_contract_id", sa.UUID(), nullable=False),
        sa.Column("payment_plan_id", sa.UUID(), nullable=False),
        sa.Column("restructure_number", sa.String(length=32), nullable=False),
        sa.Column("source_version_id", sa.UUID(), nullable=False),
        sa.Column("replacement_version_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("reason", sa.String(length=2000), nullable=False),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("requested_by_user_id", sa.UUID(), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("applied_by_user_id", sa.UUID(), nullable=True),
        sa.Column("abandoned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("abandoned_by_user_id", sa.UUID(), nullable=True),
        sa.Column("abandonment_reason", sa.String(length=500), nullable=True),
        sa.CheckConstraint(
            "status <> 'abandoned' OR (abandoned_at IS NOT NULL AND abandoned_by_user_id IS "
            "NOT NULL AND abandonment_reason IS NOT NULL)",
            name=op.f("ck_collection_restructures_abandoned_has_reason"),
        ),
        sa.CheckConstraint(
            "status <> 'applied' OR (applied_at IS NOT NULL AND applied_by_user_id IS NOT NULL)",
            name=op.f("ck_collection_restructures_applied_has_actor"),
        ),
        sa.CheckConstraint(
            "status IN ('open', 'applied', 'abandoned')",
            name=op.f("ck_collection_restructures_status_ok"),
        ),
        sa.CheckConstraint(
            "length(reason) > 0", name=op.f("ck_collection_restructures_reason_not_blank")
        ),
        sa.CheckConstraint(
            "source_version_id <> replacement_version_id",
            name=op.f("ck_collection_restructures_versions_differ"),
        ),
        sa.ForeignKeyConstraint(
            ["abandoned_by_user_id"],
            ["users.id"],
            name=op.f("fk_collection_restructures_abandoned_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["applied_by_user_id"],
            ["users.id"],
            name=op.f("fk_collection_restructures_applied_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["payment_plan_id", "project_id"],
            ["payment_plans.id", "payment_plans.project_id"],
            name="plan",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["replacement_version_id", "project_id"],
            ["payment_plan_versions.id", "payment_plan_versions.project_id"],
            name="replacement",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_user_id"],
            ["users.id"],
            name=op.f("fk_collection_restructures_requested_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["sale_contract_id", "project_id"],
            ["sale_contracts.id", "sale_contracts.project_id"],
            name="sale",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_version_id", "project_id"],
            ["payment_plan_versions.id", "payment_plan_versions.project_id"],
            name="source",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_collection_restructures")),
        sa.UniqueConstraint("id", "project_id", name="collection_restructure_project"),
        sa.UniqueConstraint(
            "project_id", "restructure_number", name="uq_collection_restructures_number"
        ),
    )
    op.create_index(
        "ix_collection_restructures_plan_status",
        "collection_restructures",
        ["payment_plan_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_collection_restructures_project_id",
        "collection_restructures",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "uq_collection_restructures_open",
        "collection_restructures",
        ["payment_plan_id"],
        unique=True,
        postgresql_where=sa.text("status = 'open'"),
    )
    op.create_table(
        "collection_actions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("sale_contract_id", sa.UUID(), nullable=False),
        sa.Column("installment_id", sa.UUID(), nullable=True),
        sa.Column("action_type", sa.String(length=32), nullable=False),
        sa.Column("action_at", sa.Date(), nullable=False),
        sa.Column("notes", sa.String(length=2000), nullable=False),
        sa.Column("promised_amount", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("promised_date", sa.Date(), nullable=True),
        sa.Column("next_action_date", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "action_type IN ('call', 'email', 'meeting', 'reminder', 'formal_notice', "
            "'promise_to_pay', 'legal_referral', 'follow_up', 'other')",
            name=op.f("ck_collection_actions_type_ok"),
        ),
        sa.CheckConstraint("length(notes) > 0", name=op.f("ck_collection_actions_notes_not_blank")),
        sa.CheckConstraint(
            "promised_amount IS NULL OR promised_amount > 0",
            name=op.f("ck_collection_actions_promise_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_collection_actions_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["installment_id", "project_id"],
            ["payment_plan_installments.id", "payment_plan_installments.project_id"],
            name="installment",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["sale_contract_id", "project_id"],
            ["sale_contracts.id", "sale_contracts.project_id"],
            name="sale",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_collection_actions")),
        sa.UniqueConstraint("id", "project_id", name="collection_action_project"),
    )
    op.create_index(
        "ix_collection_actions_next_action_date",
        "collection_actions",
        ["next_action_date"],
        unique=False,
    )
    op.create_index(
        "ix_collection_actions_project_id", "collection_actions", ["project_id"], unique=False
    )
    op.create_index(
        "ix_collection_actions_sale_action_at",
        "collection_actions",
        ["sale_contract_id", "action_at"],
        unique=False,
    )
    op.create_table(
        "collection_disputes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("sale_contract_id", sa.UUID(), nullable=False),
        sa.Column("installment_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("reason", sa.String(length=2000), nullable=False),
        sa.Column(
            "opened_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("opened_by_user_id", sa.UUID(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by_user_id", sa.UUID(), nullable=True),
        sa.Column("resolution", sa.String(length=2000), nullable=True),
        sa.CheckConstraint(
            "status = 'open' OR (resolved_at IS NOT NULL AND resolved_by_user_id IS NOT NULL)",
            name=op.f("ck_collection_disputes_closed_has_actor"),
        ),
        sa.CheckConstraint(
            "status IN ('open', 'resolved', 'withdrawn')",
            name=op.f("ck_collection_disputes_status_ok"),
        ),
        sa.CheckConstraint(
            "length(reason) > 0", name=op.f("ck_collection_disputes_reason_not_blank")
        ),
        sa.ForeignKeyConstraint(
            ["installment_id", "project_id"],
            ["payment_plan_installments.id", "payment_plan_installments.project_id"],
            name="installment",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["opened_by_user_id"],
            ["users.id"],
            name=op.f("fk_collection_disputes_opened_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["resolved_by_user_id"],
            ["users.id"],
            name=op.f("fk_collection_disputes_resolved_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["sale_contract_id", "project_id"],
            ["sale_contracts.id", "sale_contracts.project_id"],
            name="sale",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_collection_disputes")),
        sa.UniqueConstraint("id", "project_id", name="collection_dispute_project"),
    )
    op.create_index(
        "ix_collection_disputes_project_id", "collection_disputes", ["project_id"], unique=False
    )
    op.create_index(
        "ix_collection_disputes_sale_status",
        "collection_disputes",
        ["sale_contract_id", "status"],
        unique=False,
    )
    op.create_index(
        "uq_collection_disputes_open",
        "collection_disputes",
        ["installment_id"],
        unique=True,
        postgresql_where=sa.text("status = 'open'"),
    )
    op.create_table(
        "collection_receipt_allocations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("sale_contract_id", sa.UUID(), nullable=False),
        sa.Column("payment_plan_id", sa.UUID(), nullable=False),
        sa.Column("payment_plan_version_id", sa.UUID(), nullable=False),
        sa.Column("installment_id", sa.UUID(), nullable=False),
        sa.Column("receipt_id", sa.UUID(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reversed_by_user_id", sa.UUID(), nullable=True),
        sa.Column("reversal_reason", sa.String(length=500), nullable=True),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_by_restructure_id", sa.UUID(), nullable=True),
        sa.CheckConstraint(
            "status <> 'reversed' OR (reversed_at IS NOT NULL AND reversed_by_user_id IS NOT "
            "NULL AND reversal_reason IS NOT NULL)",
            name=op.f("ck_collection_receipt_allocations_reversed_has_reason"),
        ),
        sa.CheckConstraint(
            "status <> 'superseded' OR (superseded_at IS NOT NULL AND "
            "superseded_by_restructure_id IS NOT NULL)",
            name=op.f("ck_collection_receipt_allocations_superseded_has_cause"),
        ),
        sa.CheckConstraint(
            "status IN ('active', 'superseded', 'reversed')",
            name=op.f("ck_collection_receipt_allocations_status_ok"),
        ),
        sa.CheckConstraint(
            "amount > 0", name=op.f("ck_collection_receipt_allocations_amount_positive")
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_collection_receipt_allocations_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["installment_id", "project_id"],
            ["payment_plan_installments.id", "payment_plan_installments.project_id"],
            name="installment",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["payment_plan_id", "project_id"],
            ["payment_plans.id", "payment_plans.project_id"],
            name="plan",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["payment_plan_version_id", "project_id"],
            ["payment_plan_versions.id", "payment_plan_versions.project_id"],
            name="version",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["receipt_id", "project_id"],
            ["collection_receipts.id", "collection_receipts.project_id"],
            name="receipt",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reversed_by_user_id"],
            ["users.id"],
            name=op.f("fk_collection_receipt_allocations_reversed_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["sale_contract_id", "project_id"],
            ["sale_contracts.id", "sale_contracts.project_id"],
            name="sale",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["superseded_by_restructure_id", "project_id"],
            ["collection_restructures.id", "collection_restructures.project_id"],
            name="restructure",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_collection_receipt_allocations")),
        sa.UniqueConstraint("id", "project_id", name="collection_allocation_project"),
    )
    op.create_index(
        "ix_collection_allocations_installment",
        "collection_receipt_allocations",
        ["installment_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_collection_allocations_project_id",
        "collection_receipt_allocations",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_collection_allocations_receipt",
        "collection_receipt_allocations",
        ["receipt_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_collection_allocations_sale",
        "collection_receipt_allocations",
        ["sale_contract_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_collection_allocations_version",
        "collection_receipt_allocations",
        ["payment_plan_version_id", "status"],
        unique=False,
    )
    op.create_table(
        "collection_waivers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("sale_contract_id", sa.UUID(), nullable=False),
        sa.Column("installment_id", sa.UUID(), nullable=False),
        sa.Column("waiver_type", sa.String(length=24), nullable=False),
        sa.Column("waived_until", sa.Date(), nullable=False),
        sa.Column("reason", sa.String(length=2000), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("submitted_by_user_id", sa.UUID(), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by_user_id", sa.UUID(), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_by_user_id", sa.UUID(), nullable=True),
        sa.Column("rejection_reason", sa.String(length=500), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by_user_id", sa.UUID(), nullable=True),
        sa.Column("revocation_reason", sa.String(length=500), nullable=True),
        sa.CheckConstraint(
            "status <> 'approved' OR (approved_at IS NOT NULL AND approved_by_user_id IS NOT NULL)",
            name=op.f("ck_collection_waivers_approved_has_actor"),
        ),
        sa.CheckConstraint(
            "status <> 'rejected' OR (rejected_at IS NOT NULL AND rejected_by_user_id IS NOT "
            "NULL AND rejection_reason IS NOT NULL)",
            name=op.f("ck_collection_waivers_rejected_has_reason"),
        ),
        sa.CheckConstraint(
            "status <> 'revoked' OR (revoked_at IS NOT NULL AND revoked_by_user_id IS NOT NULL "
            "AND revocation_reason IS NOT NULL)",
            name=op.f("ck_collection_waivers_revoked_has_reason"),
        ),
        sa.CheckConstraint(
            "status IN ('submitted', 'approved', 'rejected', 'revoked')",
            name=op.f("ck_collection_waivers_status_ok"),
        ),
        sa.CheckConstraint(
            "waiver_type IN ('collection_hold', 'grace_extension')",
            name=op.f("ck_collection_waivers_type_ok"),
        ),
        sa.CheckConstraint(
            "length(reason) > 0", name=op.f("ck_collection_waivers_reason_not_blank")
        ),
        sa.ForeignKeyConstraint(
            ["approved_by_user_id"],
            ["users.id"],
            name=op.f("fk_collection_waivers_approved_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["installment_id", "project_id"],
            ["payment_plan_installments.id", "payment_plan_installments.project_id"],
            name="installment",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["rejected_by_user_id"],
            ["users.id"],
            name=op.f("fk_collection_waivers_rejected_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["revoked_by_user_id"],
            ["users.id"],
            name=op.f("fk_collection_waivers_revoked_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["sale_contract_id", "project_id"],
            ["sale_contracts.id", "sale_contracts.project_id"],
            name="sale",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["submitted_by_user_id"],
            ["users.id"],
            name=op.f("fk_collection_waivers_submitted_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_collection_waivers")),
        sa.UniqueConstraint("id", "project_id", name="collection_waiver_project"),
    )
    op.create_index(
        "ix_collection_waivers_project_id", "collection_waivers", ["project_id"], unique=False
    )
    op.create_index(
        "ix_collection_waivers_sale_status",
        "collection_waivers",
        ["sale_contract_id", "status"],
        unique=False,
    )
    op.create_index(
        "uq_collection_waivers_live",
        "collection_waivers",
        ["installment_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('submitted', 'approved')"),
    )
    op.add_column(
        "payment_plans",
        sa.Column("collections_started_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Revert this revision."""
    op.drop_column("payment_plans", "collections_started_at")
    op.drop_index(
        "uq_collection_waivers_live",
        table_name="collection_waivers",
        postgresql_where=sa.text("status IN ('submitted', 'approved')"),
    )
    op.drop_index("ix_collection_waivers_sale_status", table_name="collection_waivers")
    op.drop_index("ix_collection_waivers_project_id", table_name="collection_waivers")
    op.drop_table("collection_waivers")
    op.drop_index("ix_collection_allocations_version", table_name="collection_receipt_allocations")
    op.drop_index("ix_collection_allocations_sale", table_name="collection_receipt_allocations")
    op.drop_index("ix_collection_allocations_receipt", table_name="collection_receipt_allocations")
    op.drop_index(
        "ix_collection_allocations_project_id", table_name="collection_receipt_allocations"
    )
    op.drop_index(
        "ix_collection_allocations_installment", table_name="collection_receipt_allocations"
    )
    op.drop_table("collection_receipt_allocations")
    op.drop_index(
        "uq_collection_disputes_open",
        table_name="collection_disputes",
        postgresql_where=sa.text("status = 'open'"),
    )
    op.drop_index("ix_collection_disputes_sale_status", table_name="collection_disputes")
    op.drop_index("ix_collection_disputes_project_id", table_name="collection_disputes")
    op.drop_table("collection_disputes")
    op.drop_index("ix_collection_actions_sale_action_at", table_name="collection_actions")
    op.drop_index("ix_collection_actions_project_id", table_name="collection_actions")
    op.drop_index("ix_collection_actions_next_action_date", table_name="collection_actions")
    op.drop_table("collection_actions")
    op.drop_index(
        "uq_collection_restructures_open",
        table_name="collection_restructures",
        postgresql_where=sa.text("status = 'open'"),
    )
    op.drop_index("ix_collection_restructures_project_id", table_name="collection_restructures")
    op.drop_index("ix_collection_restructures_plan_status", table_name="collection_restructures")
    op.drop_table("collection_restructures")
    op.drop_index("ix_collection_refunds_sale_status", table_name="collection_refunds")
    op.drop_index("ix_collection_refunds_project_id", table_name="collection_refunds")
    op.drop_index("ix_collection_refunds_cancellation", table_name="collection_refunds")
    op.drop_table("collection_refunds")
    op.drop_index("ix_collection_receipts_sale_status", table_name="collection_receipts")
    op.drop_index("ix_collection_receipts_receipt_date", table_name="collection_receipts")
    op.drop_index("ix_collection_receipts_project_id", table_name="collection_receipts")
    op.drop_table("collection_receipts")
