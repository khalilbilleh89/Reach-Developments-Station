"""Explicit agreed-price intent and server-managed negotiation adjustments."""

import sqlalchemy as sa
from alembic import op

revision = "0021_sales_negotiated_price"
down_revision = "0020_management_reporting"
branch_labels = None
depends_on = None

OLD_TYPES = (
    "percentage_discount",
    "fixed_discount",
    "seller_credit",
    "package_cost",
    "upgrade_allowance",
    "commission_support",
    "financing_subsidy",
    "extended_terms_npv_cost",
    "paid_upgrade",
    "payment_plan_adjustment",
)


def _checks(negotiated: bool) -> None:
    types = (
        (*OLD_TYPES, "negotiated_price_discount", "negotiated_price_premium")
        if negotiated
        else OLD_TYPES
    )
    concession = "'percentage_discount', 'fixed_discount', 'seller_credit'"
    addition = "'paid_upgrade', 'payment_plan_adjustment'"
    if negotiated:
        concession += ", 'negotiated_price_discount'"
        addition += ", 'negotiated_price_premium'"
    op.create_check_constraint(
        op.f("ck_reservation_adjustments_type_ok"),
        "reservation_adjustments",
        "adjustment_type IN (" + ", ".join(repr(item) for item in types) + ")",
    )
    op.create_check_constraint(
        op.f("ck_reservation_adjustments_treatment_matches_type"),
        "reservation_adjustments",
        f"(adjustment_type IN ({concession}) AND treatment = 'price_concession') "
        "OR (adjustment_type IN ('package_cost', 'upgrade_allowance', 'commission_support', "
        "'financing_subsidy', 'extended_terms_npv_cost') AND treatment = 'seller_cost') "
        f"OR (adjustment_type IN ({addition}) AND treatment = 'price_addition')",
    )


def _drop_checks() -> None:
    for suffix in ("type_ok", "treatment_matches_type"):
        op.drop_constraint(
            op.f(f"ck_reservation_adjustments_{suffix}"), "reservation_adjustments", type_="check"
        )


def upgrade() -> None:
    op.add_column("reservations", sa.Column("creation_request_id", sa.Uuid(), nullable=True))
    op.add_column(
        "reservations", sa.Column("creation_request_fingerprint", sa.String(64), nullable=True)
    )
    op.create_unique_constraint(
        "uq_reservation_creation_request", "reservations", ["project_id", "creation_request_id"]
    )
    op.add_column(
        "reservations", sa.Column("agreed_price_target_ex_tax", sa.Numeric(18, 2), nullable=True)
    )
    op.create_check_constraint(
        op.f("ck_reservations_target_nonneg"),
        "reservations",
        "agreed_price_target_ex_tax IS NULL OR agreed_price_target_ex_tax >= 0",
    )
    _drop_checks()
    _checks(True)


def downgrade() -> None:
    # Never discard commercial decisions merely to make a rollback succeed.
    bind = op.get_bind()
    if bind.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM reservations "
            "WHERE agreed_price_target_ex_tax IS NOT NULL) "
            "OR EXISTS (SELECT 1 FROM reservation_adjustments WHERE adjustment_type "
            "IN ('negotiated_price_discount', 'negotiated_price_premium'))"
        )
    ).scalar():
        raise RuntimeError(
            "Negotiated sales decisions exist. Retain this schema; "
            "do not erase commercial history to downgrade."
        )
    _drop_checks()
    _checks(False)
    op.drop_constraint(op.f("ck_reservations_target_nonneg"), "reservations", type_="check")
    op.drop_column("reservations", "agreed_price_target_ex_tax")
    op.drop_constraint("uq_reservation_creation_request", "reservations", type_="unique")
    op.drop_column("reservations", "creation_request_fingerprint")
    op.drop_column("reservations", "creation_request_id")
