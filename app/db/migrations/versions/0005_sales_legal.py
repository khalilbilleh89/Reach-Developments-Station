"""Sales and legal: clients, reservations, sale contracts, cancellation, handover.

Adds the thirteen tables PR-MVP-05 needs, and changes exactly two things that
already existed: the closed sets behind ``units.commercial_status`` and
``units.legal_status``.

PR-MVP-03 created both columns and said plainly that the transitions belong to
Sales / Legal. It could only guess at the vocabulary, because the transactions
that produce those states did not exist yet. This revision states them as the
sales and legal timeline actually runs, so the commercial set gains
``contract_pending`` and ``withdrawn``, and the legal set is replaced outright.

``not_started`` becomes ``no_spa`` — the same fact, named for the document whose
absence it describes. Every unit already carrying it is renamed in place, before
the new constraint goes on, so no row is ever momentarily illegal. Nothing else
about a unit is touched: not its identity, hierarchy, areas, release controls,
collection or delivery status, and no price, price version or benchmark is read
or written here.

Legal status events are deleted on the way down rather than mapped, because
every one of them was written by this revision's code: before PR-MVP-05 the
inventory service wrote commercial events only. Commercial history survives
untouched — ``unit_status_events`` constrains the dimension, not the statuses.

The downgrade drops the sales tables, so a rollback loses reservations, sale
contracts, legal events, cancellations and handovers entered after the deploy.
Unit and pricing data is preserved. Statuses with no 0004 equivalent are folded
onto their nearest ancestor so the older constraints can be restored; only
``no_spa`` round trips exactly, and that is the only value a database that never
ran Sales can hold.

Five partial unique indexes carry invariants no CHECK can express: one committed
reservation per unit, one committed sale contract per unit, one SPA number per
project, one open cancellation per sale, one live clearance per handover and
type, and one reversal per legal event. Those are the backstops behind the row
locks the service takes; neither is sufficient alone.

Revision ID: 0005_sales_legal
Revises: 0004_pricing
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_sales_legal"
down_revision: str | Sequence[str] | None = "0004_pricing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: The commercial set as PR-MVP-03 deployed it, and as this revision leaves it.
COMMERCIAL_BEFORE = (
    "unreleased",
    "available",
    "held",
    "reserved",
    "contracted",
    "cancelled",
    "returned",
)
COMMERCIAL_AFTER = (
    "unreleased",
    "available",
    "held",
    "reserved",
    "contract_pending",
    "contracted",
    "cancelled",
    "returned",
    "withdrawn",
)

#: The legal set, likewise.
LEGAL_BEFORE = (
    "not_started",
    "eligible",
    "spa_in_progress",
    "spa_signed",
    "registration_in_progress",
    "registered",
    "title_transferred",
    "cancelled",
)
LEGAL_AFTER = (
    "no_spa",
    "drafting",
    "issued",
    "buyer_signed",
    "fully_signed",
    "stamped",
    "lodged_submitted",
    "registered",
    "transfer_pending",
    "transferred",
    "withdrawal_pending",
    "withdrawn",
)

#: Where each 0005 status lands if the revision is rolled back. Total, so the
#: downgrade cannot leave a row the restored constraint refuses. Lossy for
#: everything except ``no_spa``: a rolled-back database cannot describe a
#: stamped SPA, because 0004 had no word for one.
LEGAL_ROLLBACK = {
    "no_spa": "not_started",
    "drafting": "spa_in_progress",
    "issued": "spa_in_progress",
    "buyer_signed": "spa_signed",
    "fully_signed": "spa_signed",
    "stamped": "spa_signed",
    "lodged_submitted": "registration_in_progress",
    "registered": "registered",
    "transfer_pending": "registered",
    "transferred": "title_transferred",
    "withdrawal_pending": "cancelled",
    "withdrawn": "cancelled",
}
COMMERCIAL_ROLLBACK = {
    "contract_pending": "reserved",
    "withdrawn": "cancelled",
}


def _in_list(column: str, allowed: Sequence[str]) -> str:
    """Render a closed-set CHECK the same way ``app.db.types.in_list`` does."""
    values = ", ".join(f"'{value}'" for value in allowed)
    return f"{column} IN ({values})"


def upgrade() -> None:
    """Apply this revision."""
    _restate_unit_status_sets()
    _create_sales_tables()


def _restate_unit_status_sets() -> None:
    """Widen the commercial set and replace the legal one, renaming in place.

    The rename runs while no constraint governs the column, so a unit is never
    momentarily illegal, and it runs inside the migration's own transaction, so
    a failure anywhere later leaves the old vocabulary intact.
    """
    op.drop_constraint("commercial_ok", "units", type_="check")
    op.create_check_constraint(
        "commercial_ok", "units", _in_list("commercial_status", COMMERCIAL_AFTER)
    )

    op.drop_constraint("legal_ok", "units", type_="check")
    op.execute(
        sa.text("UPDATE units SET legal_status = 'no_spa' WHERE legal_status = 'not_started'")
    )
    op.create_check_constraint("legal_ok", "units", _in_list("legal_status", LEGAL_AFTER))


def _create_sales_tables() -> None:
    """Create the thirteen tables this revision owns."""
    op.create_table(
        "clients",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("client_number", sa.String(length=32), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("address", sa.String(length=500), nullable=True),
        sa.Column("preferred_language_code", sa.String(length=64), nullable=True),
        sa.Column("kyc_status", sa.String(length=16), nullable=False),
        sa.Column("privacy_consent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("privacy_consent_reference", sa.String(length=200), nullable=True),
        sa.Column("owner_advisor_user_id", sa.UUID(), nullable=True),
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
        sa.Column("updated_by_user_id", sa.UUID(), nullable=True),
        sa.CheckConstraint(
            "kyc_status IN ('not_started', 'in_progress', 'cleared', 'rejected')",
            name=op.f("ck_clients_kyc_ok"),
        ),
        sa.CheckConstraint("length(client_number) > 0", name=op.f("ck_clients_number_not_blank")),
        sa.CheckConstraint("length(display_name) > 0", name=op.f("ck_clients_name_not_blank")),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_clients_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["owner_advisor_user_id"],
            ["users.id"],
            name=op.f("fk_clients_owner_advisor_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_clients_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"],
            ["users.id"],
            name=op.f("fk_clients_updated_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_clients")),
        sa.UniqueConstraint("id", "project_id", name="client_project"),
        sa.UniqueConstraint("project_id", "client_number", name="uq_clients_number"),
    )
    op.create_index(
        "ix_clients_owner_advisor_user_id", "clients", ["owner_advisor_user_id"], unique=False
    )
    op.create_index(
        "ix_clients_project_id_is_active", "clients", ["project_id", "is_active"], unique=False
    )
    op.create_table(
        "sales_project_policies",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("handover_requires_collection_clearance", sa.Boolean(), nullable=False),
        sa.Column("handover_requires_legal_clearance", sa.Boolean(), nullable=False),
        sa.Column("handover_requires_delivery_clearance", sa.Boolean(), nullable=False),
        sa.Column("handover_requires_title_transfer", sa.Boolean(), nullable=False),
        sa.Column("title_transfer_requires_collection_clearance", sa.Boolean(), nullable=False),
        sa.Column("reservation_requires_deposit_confirmation", sa.Boolean(), nullable=False),
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
        sa.Column("updated_by_user_id", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_sales_project_policies_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"],
            ["users.id"],
            name=op.f("fk_sales_project_policies_updated_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sales_project_policies")),
        sa.UniqueConstraint("project_id", name="uq_sales_policy_project"),
    )
    op.create_table(
        "client_parties",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("client_id", sa.UUID(), nullable=False),
        sa.Column("party_role", sa.String(length=16), nullable=False),
        sa.Column("name_as_identification", sa.String(length=200), nullable=False),
        sa.Column("nationality_code", sa.String(length=64), nullable=True),
        sa.Column("residency_code", sa.String(length=64), nullable=True),
        sa.Column("tax_id", sa.String(length=64), nullable=True),
        sa.Column("identity_document_type", sa.String(length=64), nullable=True),
        sa.Column("identity_document_number", sa.String(length=64), nullable=True),
        sa.Column("share_fraction", sa.Numeric(precision=9, scale=6), nullable=False),
        sa.Column("representative_name", sa.String(length=200), nullable=True),
        sa.Column("poa_reference", sa.String(length=200), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
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
            "party_role IN ('purchaser', 'joint_purchaser')", name=op.f("ck_client_parties_role_ok")
        ),
        sa.CheckConstraint(
            "length(name_as_identification) > 0", name=op.f("ck_client_parties_name_not_blank")
        ),
        sa.CheckConstraint(
            "share_fraction > 0 AND share_fraction <= 1", name=op.f("ck_client_parties_share_range")
        ),
        sa.ForeignKeyConstraint(
            ["client_id", "project_id"],
            ["clients.id", "clients.project_id"],
            name="client",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_client_parties_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_client_parties")),
        sa.UniqueConstraint("id", "project_id", name="party_project"),
    )
    op.create_index("ix_client_parties_client_id", "client_parties", ["client_id"], unique=False)
    op.create_table(
        "reservations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("reservation_number", sa.String(length=32), nullable=False),
        sa.Column("unit_id", sa.UUID(), nullable=False),
        sa.Column("client_id", sa.UUID(), nullable=False),
        sa.Column("unit_price_version_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("reservation_date", sa.Date(), nullable=False),
        sa.Column("expires_on", sa.Date(), nullable=False),
        sa.Column("price_locked_until", sa.Date(), nullable=False),
        sa.Column("sales_channel_code", sa.String(length=64), nullable=True),
        sa.Column("sales_branch_code", sa.String(length=64), nullable=True),
        sa.Column("advisor_user_id", sa.UUID(), nullable=True),
        sa.Column("deposit_required_amount", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("deposit_currency_id", sa.UUID(), nullable=True),
        sa.Column("deposit_gate_status", sa.String(length=16), nullable=False),
        sa.Column("deposit_confirmation_reference", sa.String(length=200), nullable=True),
        sa.Column("deposit_confirmed_by_user_id", sa.UUID(), nullable=True),
        sa.Column("deposit_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deposit_waiver_reason", sa.String(length=500), nullable=True),
        sa.Column("currency_id", sa.UUID(), nullable=False),
        sa.Column("reference_price_ex_tax", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("paid_upgrade_amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column(
            "payment_plan_adjustment_amount", sa.Numeric(precision=18, scale=2), nullable=False
        ),
        sa.Column("gross_quoted_price_ex_tax", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("cash_discount_amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("seller_credit_amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("net_contract_price_ex_tax", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("seller_cost_total", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column(
            "effective_net_revenue_preview", sa.Numeric(precision=18, scale=2), nullable=False
        ),
        sa.Column("tax_total", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("buyer_fee_total", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("total_buyer_payable", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("exception_approval_required", sa.Boolean(), nullable=False),
        sa.Column("exception_approval_status", sa.String(length=16), nullable=False),
        sa.Column("exception_reason", sa.String(length=1000), nullable=True),
        sa.Column("exception_required_role", sa.String(length=32), nullable=True),
        sa.Column("exception_submitted_by_user_id", sa.UUID(), nullable=True),
        sa.Column("exception_submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exception_approved_by_user_id", sa.UUID(), nullable=True),
        sa.Column("exception_approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exception_decision_reason", sa.String(length=1000), nullable=True),
        sa.Column("quote_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("converted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closure_reason", sa.String(length=1000), nullable=True),
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
            "deposit_gate_status <> 'waived' OR deposit_waiver_reason IS NOT NULL",
            name=op.f("ck_reservations_waiver_has_reason"),
        ),
        sa.CheckConstraint(
            "deposit_gate_status IN ('not_required', 'pending', 'confirmed', 'waived')",
            name=op.f("ck_reservations_deposit_gate_ok"),
        ),
        sa.CheckConstraint(
            "exception_approval_status IN ('not_required', 'pending', 'submitted', 'approved', "
            "'rejected')",
            name=op.f("ck_reservations_exception_ok"),
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'deposit_pending', 'active', 'extended', 'converted', 'expired', "
            "'cancelled')",
            name=op.f("ck_reservations_status_ok"),
        ),
        sa.CheckConstraint(
            "deposit_required_amount IS NULL OR deposit_required_amount >= 0",
            name=op.f("ck_reservations_deposit_nonneg"),
        ),
        sa.CheckConstraint(
            "expires_on >= reservation_date", name=op.f("ck_reservations_expiry_after_start")
        ),
        sa.CheckConstraint(
            "gross_quoted_price_ex_tax >= 0", name=op.f("ck_reservations_gross_nonneg")
        ),
        sa.CheckConstraint(
            "net_contract_price_ex_tax >= 0", name=op.f("ck_reservations_net_nonneg")
        ),
        sa.CheckConstraint(
            "price_locked_until >= reservation_date", name=op.f("ck_reservations_lock_after_start")
        ),
        sa.CheckConstraint(
            "reference_price_ex_tax >= 0", name=op.f("ck_reservations_reference_nonneg")
        ),
        sa.CheckConstraint(
            "seller_cost_total >= 0", name=op.f("ck_reservations_seller_cost_nonneg")
        ),
        sa.CheckConstraint("tax_total >= 0", name=op.f("ck_reservations_tax_nonneg")),
        sa.CheckConstraint("total_buyer_payable >= 0", name=op.f("ck_reservations_payable_nonneg")),
        sa.ForeignKeyConstraint(
            ["advisor_user_id"],
            ["users.id"],
            name=op.f("fk_reservations_advisor_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["client_id", "project_id"],
            ["clients.id", "clients.project_id"],
            name="client",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_reservations_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["currency_id"],
            ["currencies.id"],
            name=op.f("fk_reservations_currency_id_currencies"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["deposit_confirmed_by_user_id"],
            ["users.id"],
            name=op.f("fk_reservations_deposit_confirmed_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["deposit_currency_id"],
            ["currencies.id"],
            name=op.f("fk_reservations_deposit_currency_id_currencies"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["exception_approved_by_user_id"],
            ["users.id"],
            name=op.f("fk_reservations_exception_approved_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["exception_submitted_by_user_id"],
            ["users.id"],
            name=op.f("fk_reservations_exception_submitted_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_reservations_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["unit_id", "project_id"],
            ["units.id", "units.project_id"],
            name="unit",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["unit_price_version_id", "project_id"],
            ["unit_price_versions.id", "unit_price_versions.project_id"],
            name="price_version",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reservations")),
        sa.UniqueConstraint("id", "project_id", name="reservation_project"),
        sa.UniqueConstraint("project_id", "reservation_number", name="uq_reservations_number"),
    )
    op.create_index("ix_reservations_client_id", "reservations", ["client_id"], unique=False)
    op.create_index(
        "ix_reservations_project_id_status", "reservations", ["project_id", "status"], unique=False
    )
    op.create_index("ix_reservations_unit_id", "reservations", ["unit_id"], unique=False)
    op.create_index(
        "uq_reservations_committed_unit",
        "reservations",
        ["unit_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('active', 'extended')"),
    )
    op.create_table(
        "reservation_adjustments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("reservation_id", sa.UUID(), nullable=False),
        sa.Column("adjustment_type", sa.String(length=32), nullable=False),
        sa.Column("treatment", sa.String(length=16), nullable=False),
        sa.Column("rate_fraction", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("reason", sa.String(length=1000), nullable=True),
        sa.Column("requested_by_user_id", sa.UUID(), nullable=False),
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
            "(adjustment_type IN ('percentage_discount', 'fixed_discount', 'seller_credit') AND "
            "treatment = 'price_concession') OR (adjustment_type IN ('package_cost', "
            "'upgrade_allowance', 'commission_support', 'financing_subsidy', "
            "'extended_terms_npv_cost') AND treatment = 'seller_cost') OR (adjustment_type IN "
            "('paid_upgrade', 'payment_plan_adjustment') AND treatment = 'price_addition')",
            name=op.f("ck_reservation_adjustments_treatment_matches_type"),
        ),
        sa.CheckConstraint(
            "(adjustment_type IN ('percentage_discount', 'payment_plan_adjustment') AND "
            "rate_fraction IS NOT NULL AND amount IS NULL) OR (adjustment_type NOT IN "
            "('percentage_discount', 'payment_plan_adjustment') AND amount IS NOT NULL AND "
            "rate_fraction IS NULL)",
            name=op.f("ck_reservation_adjustments_shape_ok"),
        ),
        sa.CheckConstraint(
            "adjustment_type IN ('percentage_discount', 'fixed_discount', 'seller_credit', "
            "'package_cost', 'upgrade_allowance', 'commission_support', 'financing_subsidy', "
            "'extended_terms_npv_cost', 'paid_upgrade', 'payment_plan_adjustment')",
            name=op.f("ck_reservation_adjustments_type_ok"),
        ),
        sa.CheckConstraint(
            "treatment IN ('price_concession', 'seller_cost', 'price_addition')",
            name=op.f("ck_reservation_adjustments_treatment_ok"),
        ),
        sa.CheckConstraint(
            "amount IS NULL OR amount >= 0", name=op.f("ck_reservation_adjustments_amount_nonneg")
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_user_id"],
            ["users.id"],
            name=op.f("fk_reservation_adjustments_requested_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reservation_id", "project_id"],
            ["reservations.id", "reservations.project_id"],
            name="reservation",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reservation_adjustments")),
        sa.UniqueConstraint(
            "reservation_id", "adjustment_type", name="uq_reservation_adjustments_type"
        ),
    )
    op.create_index(
        "ix_reservation_adjustments_reservation_id",
        "reservation_adjustments",
        ["reservation_id"],
        unique=False,
    )
    op.create_table(
        "reservation_status_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("reservation_id", sa.UUID(), nullable=False),
        sa.Column("from_status", sa.String(length=16), nullable=False),
        sa.Column("to_status", sa.String(length=16), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("reason", sa.String(length=1000), nullable=True),
        sa.Column("actor_user_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "from_status IN ('draft', 'deposit_pending', 'active', 'extended', 'converted', "
            "'expired', 'cancelled')",
            name=op.f("ck_reservation_status_events_from_ok"),
        ),
        sa.CheckConstraint(
            "to_status IN ('draft', 'deposit_pending', 'active', 'extended', 'converted', "
            "'expired', 'cancelled')",
            name=op.f("ck_reservation_status_events_to_ok"),
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_reservation_status_events_actor_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reservation_id", "project_id"],
            ["reservations.id", "reservations.project_id"],
            name="reservation",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reservation_status_events")),
    )
    op.create_index(
        "ix_reservation_status_events_reservation_id_effective_date",
        "reservation_status_events",
        ["reservation_id", "effective_date"],
        unique=False,
    )
    op.create_table(
        "sale_contracts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("sale_number", sa.String(length=32), nullable=False),
        sa.Column("spa_number", sa.String(length=64), nullable=True),
        sa.Column("reservation_id", sa.UUID(), nullable=False),
        sa.Column("unit_id", sa.UUID(), nullable=False),
        sa.Column("client_id", sa.UUID(), nullable=False),
        sa.Column("unit_price_version_id", sa.UUID(), nullable=False),
        sa.Column("currency_id", sa.UUID(), nullable=False),
        sa.Column("contract_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("reference_price_ex_tax", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("gross_quoted_price_ex_tax", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("cash_discount_amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("seller_credit_amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("net_contract_price_ex_tax", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("seller_cost_total", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column(
            "effective_net_revenue_snapshot", sa.Numeric(precision=18, scale=2), nullable=False
        ),
        sa.Column("tax_total", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("buyer_fee_total", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("total_contract_price", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column(
            "reservation_quote_snapshot_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("sales_channel_code", sa.String(length=64), nullable=True),
        sa.Column("sales_branch_code", sa.String(length=64), nullable=True),
        sa.Column("advisor_user_id", sa.UUID(), nullable=True),
        sa.Column(
            "first_payment_required_amount", sa.Numeric(precision=18, scale=2), nullable=True
        ),
        sa.Column("first_payment_gate_status", sa.String(length=16), nullable=False),
        sa.Column("first_payment_evidence_reference", sa.String(length=200), nullable=True),
        sa.Column("first_payment_confirmed_by_user_id", sa.UUID(), nullable=True),
        sa.Column("first_payment_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_payment_waiver_reason", sa.String(length=500), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_by_user_id", sa.UUID(), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_by_user_id", sa.UUID(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
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
            "first_payment_gate_status <> 'waived' OR first_payment_waiver_reason IS NOT NULL",
            name=op.f("ck_sale_contracts_waiver_has_reason"),
        ),
        sa.CheckConstraint(
            "first_payment_gate_status IN ('not_required', 'pending', 'confirmed', 'waived')",
            name=op.f("ck_sale_contracts_first_payment_gate_ok"),
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'signature_pending', 'active', 'termination_pending', "
            "'cancelled')",
            name=op.f("ck_sale_contracts_status_ok"),
        ),
        sa.CheckConstraint(
            "first_payment_required_amount IS NULL OR first_payment_required_amount >= 0",
            name=op.f("ck_sale_contracts_first_payment_nonneg"),
        ),
        sa.CheckConstraint(
            "net_contract_price_ex_tax >= 0", name=op.f("ck_sale_contracts_net_nonneg")
        ),
        sa.CheckConstraint(
            "seller_cost_total >= 0", name=op.f("ck_sale_contracts_seller_cost_nonneg")
        ),
        sa.CheckConstraint("tax_total >= 0", name=op.f("ck_sale_contracts_tax_nonneg")),
        sa.CheckConstraint(
            "total_contract_price >= 0", name=op.f("ck_sale_contracts_total_nonneg")
        ),
        sa.ForeignKeyConstraint(
            ["activated_by_user_id"],
            ["users.id"],
            name=op.f("fk_sale_contracts_activated_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["advisor_user_id"],
            ["users.id"],
            name=op.f("fk_sale_contracts_advisor_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["client_id", "project_id"],
            ["clients.id", "clients.project_id"],
            name="client",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_sale_contracts_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["currency_id"],
            ["currencies.id"],
            name=op.f("fk_sale_contracts_currency_id_currencies"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["first_payment_confirmed_by_user_id"],
            ["users.id"],
            name=op.f("fk_sale_contracts_first_payment_confirmed_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_sale_contracts_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reservation_id", "project_id"],
            ["reservations.id", "reservations.project_id"],
            name="reservation",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["submitted_by_user_id"],
            ["users.id"],
            name=op.f("fk_sale_contracts_submitted_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["unit_id", "project_id"],
            ["units.id", "units.project_id"],
            name="unit",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["unit_price_version_id", "project_id"],
            ["unit_price_versions.id", "unit_price_versions.project_id"],
            name="price_version",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sale_contracts")),
        sa.UniqueConstraint("id", "project_id", name="sale_project"),
        sa.UniqueConstraint("project_id", "sale_number", name="uq_sale_contracts_number"),
    )
    op.create_index("ix_sale_contracts_client_id", "sale_contracts", ["client_id"], unique=False)
    op.create_index(
        "ix_sale_contracts_project_id_status",
        "sale_contracts",
        ["project_id", "status"],
        unique=False,
    )
    op.create_index("ix_sale_contracts_unit_id", "sale_contracts", ["unit_id"], unique=False)
    op.create_index(
        "uq_sale_contracts_committed_unit",
        "sale_contracts",
        ["unit_id"],
        unique=True,
        postgresql_where=sa.text(
            "status IN ('signature_pending', 'active', 'termination_pending')"
        ),
    )
    op.create_index(
        "uq_sale_contracts_spa_number",
        "sale_contracts",
        ["project_id", "spa_number"],
        unique=True,
        postgresql_where=sa.text("spa_number IS NOT NULL"),
    )
    op.create_table(
        "handover_records",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("sale_contract_id", sa.UUID(), nullable=False),
        sa.Column("readiness_date", sa.Date(), nullable=True),
        sa.Column("inspection_date", sa.Date(), nullable=True),
        sa.Column("snag_status", sa.String(length=64), nullable=True),
        sa.Column("snag_notes", sa.String(length=2000), nullable=True),
        sa.Column("client_notice_date", sa.Date(), nullable=True),
        sa.Column("scheduled_handover_date", sa.Date(), nullable=True),
        sa.Column("handover_date", sa.Date(), nullable=True),
        sa.Column("keys_reference", sa.String(length=200), nullable=True),
        sa.Column("meter_readings_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("acceptance_document_reference", sa.String(length=200), nullable=True),
        sa.Column("notes", sa.String(length=2000), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
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
        sa.Column("completed_by_user_id", sa.UUID(), nullable=True),
        sa.CheckConstraint(
            "status <> 'handed_over' OR handover_date IS NOT NULL",
            name=op.f("ck_handover_records_handover_has_date"),
        ),
        sa.CheckConstraint(
            "status IN ('preparation', 'inspection_pending', 'snagging', 'ready', 'handed_over', "
            "'cancelled')",
            name=op.f("ck_handover_records_status_ok"),
        ),
        sa.ForeignKeyConstraint(
            ["completed_by_user_id"],
            ["users.id"],
            name=op.f("fk_handover_records_completed_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_handover_records_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["sale_contract_id", "project_id"],
            ["sale_contracts.id", "sale_contracts.project_id"],
            name="sale",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_handover_records")),
        sa.UniqueConstraint("id", "project_id", name="handover_project"),
        sa.UniqueConstraint("sale_contract_id", name="uq_handover_records_sale"),
    )
    op.create_table(
        "sale_cancellations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("sale_contract_id", sa.UUID(), nullable=False),
        sa.Column("initiated_by_party", sa.String(length=32), nullable=False),
        sa.Column("initiation_date", sa.Date(), nullable=False),
        sa.Column("notice_date", sa.Date(), nullable=True),
        sa.Column("cure_deadline", sa.Date(), nullable=True),
        sa.Column("reason_code", sa.String(length=64), nullable=True),
        sa.Column("reason", sa.String(length=2000), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("termination_date", sa.Date(), nullable=True),
        sa.Column("forfeiture_amount", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("refund_due_amount", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("financial_approval_required", sa.Boolean(), nullable=False),
        sa.Column("financial_approved_by_user_id", sa.UUID(), nullable=True),
        sa.Column("financial_approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("legal_withdrawal_required", sa.Boolean(), nullable=False),
        sa.Column("legal_withdrawal_status", sa.String(length=16), nullable=False),
        sa.Column("unit_return_date", sa.Date(), nullable=True),
        sa.Column("remarketing_required", sa.Boolean(), nullable=False),
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
            "initiated_by_party IN ('buyer', 'seller', 'mutual', 'developer_default_process')",
            name=op.f("ck_sale_cancellations_initiator_ok"),
        ),
        sa.CheckConstraint(
            "legal_withdrawal_status IN ('not_required', 'pending', 'completed')",
            name=op.f("ck_sale_cancellations_withdrawal_ok"),
        ),
        sa.CheckConstraint(
            "status IN ('notice', 'cure', 'termination_pending_approval', 'withdrawal_pending', "
            "'ready_for_unit_return', 'completed', 'withdrawn')",
            name=op.f("ck_sale_cancellations_status_ok"),
        ),
        sa.CheckConstraint(
            "cure_deadline IS NULL OR notice_date IS NULL OR cure_deadline >= notice_date",
            name=op.f("ck_sale_cancellations_cure_after_notice"),
        ),
        sa.CheckConstraint(
            "forfeiture_amount IS NULL OR forfeiture_amount >= 0",
            name=op.f("ck_sale_cancellations_forfeiture_nonneg"),
        ),
        sa.CheckConstraint(
            "length(reason) > 0", name=op.f("ck_sale_cancellations_reason_not_blank")
        ),
        sa.CheckConstraint(
            "refund_due_amount IS NULL OR refund_due_amount >= 0",
            name=op.f("ck_sale_cancellations_refund_nonneg"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_sale_cancellations_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["financial_approved_by_user_id"],
            ["users.id"],
            name=op.f("fk_sale_cancellations_financial_approved_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["sale_contract_id", "project_id"],
            ["sale_contracts.id", "sale_contracts.project_id"],
            name="sale",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sale_cancellations")),
        sa.UniqueConstraint("id", "project_id", name="cancellation_project"),
    )
    op.create_index(
        "ix_sale_cancellations_sale_contract_id_status",
        "sale_cancellations",
        ["sale_contract_id", "status"],
        unique=False,
    )
    op.create_index(
        "uq_sale_cancellations_open",
        "sale_cancellations",
        ["sale_contract_id"],
        unique=True,
        postgresql_where=sa.text(
            "status IN ('notice', 'cure', 'termination_pending_approval', 'withdrawal_pending', "
            "'ready_for_unit_return')"
        ),
    )
    op.create_table(
        "sale_contract_parties",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("sale_contract_id", sa.UUID(), nullable=False),
        sa.Column("client_party_id", sa.UUID(), nullable=True),
        sa.Column("party_role", sa.String(length=16), nullable=False),
        sa.Column("name_as_identification", sa.String(length=200), nullable=False),
        sa.Column("nationality_code", sa.String(length=64), nullable=True),
        sa.Column("residency_code", sa.String(length=64), nullable=True),
        sa.Column("tax_id", sa.String(length=64), nullable=True),
        sa.Column("identity_document_type", sa.String(length=64), nullable=True),
        sa.Column("identity_document_number", sa.String(length=64), nullable=True),
        sa.Column("share_fraction", sa.Numeric(precision=9, scale=6), nullable=False),
        sa.Column("representative_name", sa.String(length=200), nullable=True),
        sa.Column("poa_reference", sa.String(length=200), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "party_role IN ('purchaser', 'joint_purchaser')",
            name=op.f("ck_sale_contract_parties_role_ok"),
        ),
        sa.CheckConstraint(
            "share_fraction > 0 AND share_fraction <= 1",
            name=op.f("ck_sale_contract_parties_share_range"),
        ),
        sa.ForeignKeyConstraint(
            ["sale_contract_id", "project_id"],
            ["sale_contracts.id", "sale_contracts.project_id"],
            name="sale",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sale_contract_parties")),
    )
    op.create_index(
        "ix_sale_contract_parties_sale_contract_id",
        "sale_contract_parties",
        ["sale_contract_id"],
        unique=False,
    )
    op.create_table(
        "sale_contract_tax_lines",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("sale_contract_id", sa.UUID(), nullable=False),
        sa.Column("tax_rule_id", sa.UUID(), nullable=True),
        sa.Column("tax_code", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("rate_fraction", sa.Numeric(precision=9, scale=6), nullable=False),
        sa.Column("calculation_basis", sa.String(length=64), nullable=False),
        sa.Column("taxable_amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("tax_amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("currency_id", sa.UUID(), nullable=False),
        sa.Column("valid_on", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("tax_amount >= 0", name=op.f("ck_sale_contract_tax_lines_tax_nonneg")),
        sa.CheckConstraint(
            "taxable_amount >= 0", name=op.f("ck_sale_contract_tax_lines_taxable_nonneg")
        ),
        sa.ForeignKeyConstraint(
            ["currency_id"],
            ["currencies.id"],
            name=op.f("fk_sale_contract_tax_lines_currency_id_currencies"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["sale_contract_id", "project_id"],
            ["sale_contracts.id", "sale_contracts.project_id"],
            name="sale",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tax_rule_id"],
            ["tax_rules.id"],
            name=op.f("fk_sale_contract_tax_lines_tax_rule_id_tax_rules"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sale_contract_tax_lines")),
    )
    op.create_index(
        "ix_sale_contract_tax_lines_sale_contract_id",
        "sale_contract_tax_lines",
        ["sale_contract_id"],
        unique=False,
    )
    op.create_table(
        "sale_legal_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("sale_contract_id", sa.UUID(), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("authority_reference", sa.String(length=200), nullable=True),
        sa.Column("document_reference", sa.String(length=200), nullable=True),
        sa.Column("fee_amount", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("currency_id", sa.UUID(), nullable=True),
        sa.Column("notes", sa.String(length=2000), nullable=True),
        sa.Column("reverses_event_id", sa.UUID(), nullable=True),
        sa.Column("reversal_reason", sa.String(length=1000), nullable=True),
        sa.Column("entered_by_user_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "event_type IN ('spa_drafted', 'spa_approved', 'spa_issued', 'buyer_signed', "
            "'seller_signed', 'stamped', 'stamp_duty_recorded', 'land_registry_lodged', "
            "'land_registry_accepted', 'registered', 'title_transfer_pending', "
            "'title_transferred', 'withdrawal_started', 'withdrawn')",
            name=op.f("ck_sale_legal_events_type_ok"),
        ),
        sa.CheckConstraint(
            "fee_amount IS NULL OR currency_id IS NOT NULL",
            name=op.f("ck_sale_legal_events_fee_has_currency"),
        ),
        sa.CheckConstraint(
            "fee_amount IS NULL OR fee_amount >= 0", name=op.f("ck_sale_legal_events_fee_nonneg")
        ),
        sa.CheckConstraint(
            "reverses_event_id IS NULL OR reversal_reason IS NOT NULL",
            name=op.f("ck_sale_legal_events_reversal_has_reason"),
        ),
        sa.ForeignKeyConstraint(
            ["currency_id"],
            ["currencies.id"],
            name=op.f("fk_sale_legal_events_currency_id_currencies"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["entered_by_user_id"],
            ["users.id"],
            name=op.f("fk_sale_legal_events_entered_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reverses_event_id"], ["sale_legal_events.id"], name="reverses", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["sale_contract_id", "project_id"],
            ["sale_contracts.id", "sale_contracts.project_id"],
            name="sale",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sale_legal_events")),
        sa.UniqueConstraint("id", "project_id", name="legal_event_project"),
    )
    op.create_index(
        "ix_sale_legal_events_sale_contract_id_event_date",
        "sale_legal_events",
        ["sale_contract_id", "event_date"],
        unique=False,
    )
    op.create_index(
        "uq_sale_legal_events_reverses",
        "sale_legal_events",
        ["reverses_event_id"],
        unique=True,
        postgresql_where=sa.text("reverses_event_id IS NOT NULL"),
    )
    op.create_table(
        "handover_clearances",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("handover_id", sa.UUID(), nullable=False),
        sa.Column("clearance_type", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("evidence_reference", sa.String(length=200), nullable=True),
        sa.Column("reason", sa.String(length=1000), nullable=True),
        sa.Column("cleared_by_user_id", sa.UUID(), nullable=True),
        sa.Column("cleared_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by_user_id", sa.UUID(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revocation_reason", sa.String(length=1000), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "clearance_type IN ('legal', 'collection', 'delivery')",
            name=op.f("ck_handover_clearances_type_ok"),
        ),
        sa.CheckConstraint(
            "status <> 'revoked' OR revocation_reason IS NOT NULL",
            name=op.f("ck_handover_clearances_revocation_has_reason"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'cleared', 'revoked')",
            name=op.f("ck_handover_clearances_status_ok"),
        ),
        sa.ForeignKeyConstraint(
            ["cleared_by_user_id"],
            ["users.id"],
            name=op.f("fk_handover_clearances_cleared_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["handover_id", "project_id"],
            ["handover_records.id", "handover_records.project_id"],
            name="handover",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["revoked_by_user_id"],
            ["users.id"],
            name=op.f("fk_handover_clearances_revoked_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_handover_clearances")),
    )
    op.create_index(
        "ix_handover_clearances_handover_id", "handover_clearances", ["handover_id"], unique=False
    )
    op.create_index(
        "uq_handover_clearances_current",
        "handover_clearances",
        ["handover_id", "clearance_type"],
        unique=True,
        postgresql_where=sa.text("status <> 'revoked'"),
    )


def downgrade() -> None:
    """Revert this revision."""
    _drop_sales_tables()
    _restore_unit_status_sets()


def _restore_unit_status_sets() -> None:
    """Put the 0004 vocabularies back, folding what they cannot express.

    Legal status events go first. Every one of them was written by this
    revision's code — before PR-MVP-05 the inventory service recorded commercial
    movements only — so deleting them removes what this revision added rather
    than history that predates it. Commercial events stay: their statuses are
    free text as far as the schema is concerned, and rewriting them could
    collapse a from/to pair into a no-op the table refuses.
    """
    op.execute(sa.text("DELETE FROM unit_status_events WHERE dimension = 'legal'"))

    op.drop_constraint("legal_ok", "units", type_="check")
    for new_value, old_value in LEGAL_ROLLBACK.items():
        op.execute(
            sa.text("UPDATE units SET legal_status = :old WHERE legal_status = :new").bindparams(
                old=old_value, new=new_value
            )
        )
    op.create_check_constraint("legal_ok", "units", _in_list("legal_status", LEGAL_BEFORE))

    op.drop_constraint("commercial_ok", "units", type_="check")
    for new_value, old_value in COMMERCIAL_ROLLBACK.items():
        op.execute(
            sa.text(
                "UPDATE units SET commercial_status = :old WHERE commercial_status = :new"
            ).bindparams(old=old_value, new=new_value)
        )
    op.create_check_constraint(
        "commercial_ok", "units", _in_list("commercial_status", COMMERCIAL_BEFORE)
    )


def _drop_sales_tables() -> None:
    """Drop the thirteen tables this revision created, children first."""
    op.drop_index(
        "uq_handover_clearances_current",
        table_name="handover_clearances",
        postgresql_where=sa.text("status <> 'revoked'"),
    )
    op.drop_index("ix_handover_clearances_handover_id", table_name="handover_clearances")
    op.drop_table("handover_clearances")
    op.drop_index(
        "uq_sale_legal_events_reverses",
        table_name="sale_legal_events",
        postgresql_where=sa.text("reverses_event_id IS NOT NULL"),
    )
    op.drop_index(
        "ix_sale_legal_events_sale_contract_id_event_date", table_name="sale_legal_events"
    )
    op.drop_table("sale_legal_events")
    op.drop_index(
        "ix_sale_contract_tax_lines_sale_contract_id", table_name="sale_contract_tax_lines"
    )
    op.drop_table("sale_contract_tax_lines")
    op.drop_index("ix_sale_contract_parties_sale_contract_id", table_name="sale_contract_parties")
    op.drop_table("sale_contract_parties")
    op.drop_index(
        "uq_sale_cancellations_open",
        table_name="sale_cancellations",
        postgresql_where=sa.text(
            "status IN ('notice', 'cure', 'termination_pending_approval', 'withdrawal_pending', "
            "'ready_for_unit_return')"
        ),
    )
    op.drop_index("ix_sale_cancellations_sale_contract_id_status", table_name="sale_cancellations")
    op.drop_table("sale_cancellations")
    op.drop_table("handover_records")
    op.drop_index(
        "uq_sale_contracts_spa_number",
        table_name="sale_contracts",
        postgresql_where=sa.text("spa_number IS NOT NULL"),
    )
    op.drop_index(
        "uq_sale_contracts_committed_unit",
        table_name="sale_contracts",
        postgresql_where=sa.text(
            "status IN ('signature_pending', 'active', 'termination_pending')"
        ),
    )
    op.drop_index("ix_sale_contracts_unit_id", table_name="sale_contracts")
    op.drop_index("ix_sale_contracts_project_id_status", table_name="sale_contracts")
    op.drop_index("ix_sale_contracts_client_id", table_name="sale_contracts")
    op.drop_table("sale_contracts")
    op.drop_index(
        "ix_reservation_status_events_reservation_id_effective_date",
        table_name="reservation_status_events",
    )
    op.drop_table("reservation_status_events")
    op.drop_index("ix_reservation_adjustments_reservation_id", table_name="reservation_adjustments")
    op.drop_table("reservation_adjustments")
    op.drop_index(
        "uq_reservations_committed_unit",
        table_name="reservations",
        postgresql_where=sa.text("status IN ('active', 'extended')"),
    )
    op.drop_index("ix_reservations_unit_id", table_name="reservations")
    op.drop_index("ix_reservations_project_id_status", table_name="reservations")
    op.drop_index("ix_reservations_client_id", table_name="reservations")
    op.drop_table("reservations")
    op.drop_index("ix_client_parties_client_id", table_name="client_parties")
    op.drop_table("client_parties")
    op.drop_table("sales_project_policies")
    op.drop_index("ix_clients_project_id_is_active", table_name="clients")
    op.drop_index("ix_clients_owner_advisor_user_id", table_name="clients")
    op.drop_table("clients")
