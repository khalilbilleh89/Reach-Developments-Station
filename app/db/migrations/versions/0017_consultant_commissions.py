"""Consultant Engineer and Commission Distribution."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0017_consultant_commissions"
down_revision = "0016_prelaunch_utilities"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "consultant_engagements",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("consultant_name", sa.String(200), nullable=False),
        sa.Column("agreement_reference", sa.String(120), nullable=False),
        sa.Column("agreement_date", sa.Date()),
        sa.Column("planned_start_date", sa.Date()),
        sa.Column("planned_completion_date", sa.Date()),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("scope_summary", sa.String(2000)),
        sa.Column("notes", sa.String(2000)),
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "project_id", name="ce_engagement_project"),
        sa.CheckConstraint(
            "length(trim(consultant_name)) > 0",
            name=op.f("ck_consultant_engagements_consultant_name_present"),
        ),
        sa.CheckConstraint(
            "length(trim(agreement_reference)) > 0",
            name=op.f("ck_consultant_engagements_agreement_ref_present"),
        ),
        sa.CheckConstraint(
            "status IN ('draft','active','completed','terminated')",
            name=op.f("ck_consultant_engagements_status_ok"),
        ),
        sa.CheckConstraint(
            "planned_start_date IS NULL OR planned_completion_date IS NULL "
            "OR planned_completion_date >= planned_start_date",
            name=op.f("ck_consultant_engagements_planned_dates_ordered"),
        ),
    )
    op.create_index(
        "uq_ce_one_active_engagement",
        "consultant_engagements",
        ["project_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_table(
        "consultant_disciplines",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("engagement_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("normalized_name", sa.String(160), nullable=False),
        sa.Column("lead_name", sa.String(200)),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("notes", sa.String(2000)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["engagement_id", "project_id"],
            ["consultant_engagements.id", "consultant_engagements.project_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "project_id", name="ce_discipline_project"),
        sa.UniqueConstraint("engagement_id", "normalized_name", name="uq_ce_discipline_name"),
        sa.CheckConstraint(
            "length(trim(name)) > 0", name=op.f("ck_consultant_disciplines_name_present")
        ),
        sa.CheckConstraint(
            "status IN ('not_started','active','completed','on_hold')",
            name=op.f("ck_consultant_disciplines_status_ok"),
        ),
    )
    op.create_table(
        "consultant_design_stages",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("engagement_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("planned_date", sa.Date()),
        sa.Column("forecast_date", sa.Date()),
        sa.Column("actual_completion_date", sa.Date()),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("notes", sa.String(2000)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["engagement_id", "project_id"],
            ["consultant_engagements.id", "consultant_engagements.project_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "project_id", name="ce_stage_project"),
        sa.UniqueConstraint("engagement_id", "sequence", name="uq_ce_stage_sequence"),
        sa.CheckConstraint(
            "length(trim(name)) > 0", name=op.f("ck_consultant_design_stages_name_present")
        ),
        sa.CheckConstraint(
            "sequence > 0", name=op.f("ck_consultant_design_stages_sequence_positive")
        ),
        sa.CheckConstraint(
            "status IN ('not_started','in_progress','completed','on_hold','cancelled')",
            name=op.f("ck_consultant_design_stages_status_ok"),
        ),
        sa.CheckConstraint(
            "status <> 'completed' OR actual_completion_date IS NOT NULL",
            name=op.f("ck_consultant_design_stages_completed_has_date"),
        ),
    )
    op.create_table(
        "consultant_deliverables",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("engagement_id", sa.UUID(), nullable=False),
        sa.Column("stage_id", sa.UUID(), nullable=False),
        sa.Column("discipline_id", sa.UUID()),
        sa.Column("name", sa.String(240), nullable=False),
        sa.Column("category", sa.String(120)),
        sa.Column("revision_reference", sa.String(120)),
        sa.Column("document_reference", sa.String(500)),
        sa.Column("due_date", sa.Date()),
        sa.Column("submitted_date", sa.Date()),
        sa.Column("accepted_date", sa.Date()),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("notes", sa.String(2000)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["engagement_id", "project_id"],
            ["consultant_engagements.id", "consultant_engagements.project_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["stage_id", "project_id"],
            ["consultant_design_stages.id", "consultant_design_stages.project_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["discipline_id", "project_id"],
            ["consultant_disciplines.id", "consultant_disciplines.project_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "length(trim(name)) > 0", name=op.f("ck_consultant_deliverables_name_present")
        ),
        sa.CheckConstraint(
            "status IN ('not_started','in_progress','submitted','accepted',"
            "'superseded','cancelled')",
            name=op.f("ck_consultant_deliverables_status_ok"),
        ),
        sa.CheckConstraint(
            "status NOT IN ('submitted','accepted') OR submitted_date IS NOT NULL",
            name=op.f("ck_consultant_deliverables_submitted_has_date"),
        ),
        sa.CheckConstraint(
            "status <> 'accepted' OR accepted_date IS NOT NULL",
            name=op.f("ck_consultant_deliverables_accepted_has_date"),
        ),
    )
    op.create_table(
        "commission_grants",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("sale_contract_id", sa.UUID(), nullable=False),
        sa.Column("unit_id", sa.UUID(), nullable=False),
        sa.Column("currency_id", sa.UUID(), nullable=False),
        sa.Column("sold_price_snapshot", sa.Numeric(18, 2), nullable=False),
        sa.Column("commissionable_base_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("granted_rate_fraction", sa.Numeric(9, 6), nullable=False),
        sa.Column("commission_total", sa.Numeric(18, 2), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("notes", sa.String(2000)),
        sa.Column("prepared_by_user_id", sa.UUID(), nullable=False),
        sa.Column("released_by_user_id", sa.UUID()),
        sa.Column("released_at", sa.DateTime(timezone=True)),
        sa.Column("reversed_by_user_id", sa.UUID()),
        sa.Column("reversed_at", sa.DateTime(timezone=True)),
        sa.Column("reversal_reason", sa.String(1000)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["sale_contract_id", "project_id"],
            ["sale_contracts.id", "sale_contracts.project_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["unit_id", "project_id"], ["units.id", "units.project_id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["currency_id"], ["currencies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["prepared_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["released_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reversed_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "project_id", name="commission_project"),
        sa.CheckConstraint(
            "sold_price_snapshot > 0", name=op.f("ck_commission_grants_sold_price_positive")
        ),
        sa.CheckConstraint(
            "commissionable_base_amount > 0 AND commissionable_base_amount <= sold_price_snapshot",
            name=op.f("ck_commission_grants_base_range"),
        ),
        sa.CheckConstraint(
            "granted_rate_fraction > 0 AND granted_rate_fraction <= 1",
            name=op.f("ck_commission_grants_rate_range"),
        ),
        sa.CheckConstraint(
            "commission_total > 0", name=op.f("ck_commission_grants_total_positive")
        ),
        sa.CheckConstraint(
            "status IN ('draft','released','reversed')", name=op.f("ck_commission_grants_status_ok")
        ),
        sa.CheckConstraint(
            "status <> 'released' OR (released_at IS NOT NULL AND released_by_user_id IS NOT NULL)",
            name=op.f("ck_commission_grants_released_has_actor"),
        ),
        sa.CheckConstraint(
            "status <> 'reversed' OR (reversed_at IS NOT NULL "
            "AND reversed_by_user_id IS NOT NULL AND reversal_reason IS NOT NULL)",
            name=op.f("ck_commission_grants_reversed_has_actor"),
        ),
        sa.CheckConstraint(
            "released_by_user_id IS NULL OR released_by_user_id <> prepared_by_user_id",
            name=op.f("ck_commission_grants_checker_differs"),
        ),
    )
    op.create_index(
        "uq_commission_live_sale",
        "commission_grants",
        ["sale_contract_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('draft','released')"),
    )
    op.create_table(
        "commission_allocations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("commission_id", sa.UUID(), nullable=False),
        sa.Column("beneficiary_name", sa.String(200), nullable=False),
        sa.Column("rate_fraction", sa.Numeric(9, 6), nullable=False),
        sa.Column("calculated_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("notes", sa.String(1000)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["commission_id", "project_id"],
            ["commission_grants.id", "commission_grants.project_id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("commission_id", "sequence", name="uq_commission_allocation_sequence"),
        sa.CheckConstraint(
            "length(trim(beneficiary_name)) > 0",
            name=op.f("ck_commission_allocations_beneficiary_present"),
        ),
        sa.CheckConstraint(
            "rate_fraction > 0 AND rate_fraction <= 1",
            name=op.f("ck_commission_allocations_rate_range"),
        ),
        sa.CheckConstraint(
            "calculated_amount > 0", name=op.f("ck_commission_allocations_amount_positive")
        ),
        sa.CheckConstraint(
            "sequence > 0", name=op.f("ck_commission_allocations_sequence_positive")
        ),
    )


def downgrade() -> None:
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM consultant_engagements) "
        "OR EXISTS (SELECT 1 FROM commission_grants) THEN RAISE EXCEPTION "
        "'cannot downgrade while consultant or commission records exist'; "
        "END IF; END $$"
    )
    op.drop_table("commission_allocations")
    op.drop_index("uq_commission_live_sale", table_name="commission_grants")
    op.drop_table("commission_grants")
    op.drop_table("consultant_deliverables")
    op.drop_table("consultant_design_stages")
    op.drop_table("consultant_disciplines")
    op.drop_index("uq_ce_one_active_engagement", table_name="consultant_engagements")
    op.drop_table("consultant_engagements")
