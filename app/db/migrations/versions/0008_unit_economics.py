"""Unit economics: allocation versions, cost pools, allocations and unit costs.

Four new tables and not one column on an existing one. That is the point worth
reading twice: a sold unit remembers which cost basis governed it, and it does
so without ``sale_contracts`` gaining a foreign key into this module. The link
is the sale's own economic contract date — the binding-signature date sales
answers for, not the drafting date — matched against a version's effective
window, which is why sales, pricing, inventory and projects are untouched here
and none of them imports unit economics.

Nothing stores a profit. There is no ``units.total_cost``, no ``units.margin``
and no project totals table, because every one of those is derivable and a
derived number kept as independent truth is a number that will disagree with its
own inputs. What *is* stored is the allocation detail — which units were
eligible, what driver each carried, which approved area schedule and which price
version supplied it, and where the rounding residual landed — because
recalculating a historical allocation from today's areas and prices would answer
a different question from the one that was approved.

``unit_economics_allocation_versions`` is created first because pools point at
it, then ``unit_economics_cost_pools``, then ``unit_economics_allocations``
which points at both, and finally ``unit_economics_unit_costs``, which points at
no version at all: a cost belonging to one unit is not divided by anything. The
downgrade drops the four in reverse and leaves collections, payment plans, sales,
pricing, inventory and projects exactly as 0007 left them.

Revision ID: 0008_unit_economics
Revises: 0007_collections
Create Date: 2026-09-02 10:07:54.637669+00:00

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_unit_economics"
down_revision: str | Sequence[str] | None = "0007_collections"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply this revision."""
    op.create_table(
        "unit_economics_allocation_versions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("currency_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("finance_treatment", sa.String(length=16), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("change_reason", sa.String(length=1000), nullable=False),
        sa.Column("source_version_id", sa.UUID(), nullable=True),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=True),
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
            "finance_treatment IN ('allocated', 'excluded')",
            name=op.f("ck_unit_economics_allocation_versions_treatment_ok"),
        ),
        sa.CheckConstraint(
            "status <> 'rejected' OR (rejected_at IS NOT NULL AND rejection_reason IS NOT NULL)",
            name=op.f("ck_unit_economics_allocation_versions_rejection_complete"),
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'submitted', 'approved', 'active', 'superseded', 'rejected')",
            name=op.f("ck_unit_economics_allocation_versions_status_ok"),
        ),
        sa.CheckConstraint(
            "status NOT IN ('active', 'superseded') OR activated_at IS NOT NULL",
            name=op.f("ck_unit_economics_allocation_versions_activation_stamped"),
        ),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to > effective_from",
            name=op.f("ck_unit_economics_allocation_versions_window_ordered"),
        ),
        sa.CheckConstraint(
            "length(change_reason) > 0",
            name=op.f("ck_unit_economics_allocation_versions_reason_present"),
        ),
        sa.CheckConstraint(
            "version_number >= 1",
            name=op.f("ck_unit_economics_allocation_versions_number_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["activated_by_user_id"],
            ["users.id"],
            name=op.f("fk_unit_economics_allocation_versions_activated_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["approved_by_user_id"],
            ["users.id"],
            name=op.f("fk_unit_economics_allocation_versions_approved_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_unit_economics_allocation_versions_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["currency_id"],
            ["currencies.id"],
            name=op.f("fk_unit_economics_allocation_versions_currency_id_currencies"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_unit_economics_allocation_versions_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["rejected_by_user_id"],
            ["users.id"],
            name=op.f("fk_unit_economics_allocation_versions_rejected_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["submitted_by_user_id"],
            ["users.id"],
            name=op.f("fk_unit_economics_allocation_versions_submitted_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_unit_economics_allocation_versions")),
        sa.UniqueConstraint("id", "project_id", name="ue_version_project"),
        sa.UniqueConstraint("project_id", "version_number", name="uq_ue_version_number"),
    )
    # Added after the table exists because it points back at the same table.
    op.create_foreign_key(
        "source_version",
        "unit_economics_allocation_versions",
        "unit_economics_allocation_versions",
        ["source_version_id", "project_id"],
        ["id", "project_id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_ue_versions_project_effective",
        "unit_economics_allocation_versions",
        ["project_id", "effective_from"],
        unique=False,
    )
    op.create_index(
        "ix_ue_versions_project_status",
        "unit_economics_allocation_versions",
        ["project_id", "status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_unit_economics_allocation_versions_project_id"),
        "unit_economics_allocation_versions",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "uq_ue_versions_one_active",
        "unit_economics_allocation_versions",
        ["project_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_table(
        "unit_economics_cost_pools",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("allocation_version_id", sa.UUID(), nullable=False),
        sa.Column("pool_number", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=16), nullable=False),
        sa.Column("source_kind", sa.String(length=16), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("scope_kind", sa.String(length=16), nullable=False),
        sa.Column("phase_id", sa.UUID(), nullable=True),
        sa.Column("building_id", sa.UUID(), nullable=True),
        sa.Column("allocation_method", sa.String(length=24), nullable=False),
        sa.Column("area_type_id", sa.UUID(), nullable=True),
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
        sa.CheckConstraint(
            "(allocation_method = 'raw_area') = (area_type_id IS NOT NULL)",
            name=op.f("ck_unit_economics_cost_pools_area_type_shape"),
        ),
        sa.CheckConstraint(
            "(scope_kind = 'project' AND phase_id IS NULL AND building_id IS NULL) "
            "OR (scope_kind = 'phase' AND phase_id IS NOT NULL AND building_id IS NULL) "
            "OR (scope_kind = 'building' AND building_id IS NOT NULL AND phase_id IS NULL)",
            name=op.f("ck_unit_economics_cost_pools_scope_shape"),
        ),
        sa.CheckConstraint(
            "allocation_method IN ('weighted_area', 'raw_area', 'unit_count', "
            "'revenue_value', 'custom_driver')",
            name=op.f("ck_unit_economics_cost_pools_method_ok"),
        ),
        sa.CheckConstraint(
            "category IN ('land', 'hard', 'soft', 'finance')",
            name=op.f("ck_unit_economics_cost_pools_category_ok"),
        ),
        sa.CheckConstraint(
            "scope_kind IN ('project', 'phase', 'building')",
            name=op.f("ck_unit_economics_cost_pools_scope_ok"),
        ),
        sa.CheckConstraint(
            "source_kind <> 'project_land' OR category = 'land'",
            name=op.f("ck_unit_economics_cost_pools_land_source_shape"),
        ),
        sa.CheckConstraint(
            "category <> 'land' OR source_kind = 'project_land'",
            name=op.f("ck_unit_economics_cost_pools_land_is_canonical"),
        ),
        sa.CheckConstraint(
            "source_kind <> 'project_land' OR scope_kind = 'project'",
            name=op.f("ck_unit_economics_cost_pools_land_is_project_wide"),
        ),
        sa.CheckConstraint(
            "source_kind IN ('project_land', 'manual')",
            name=op.f("ck_unit_economics_cost_pools_source_ok"),
        ),
        sa.CheckConstraint("amount >= 0", name=op.f("ck_unit_economics_cost_pools_amount_nonneg")),
        sa.CheckConstraint(
            "length(name) > 0", name=op.f("ck_unit_economics_cost_pools_name_present")
        ),
        sa.ForeignKeyConstraint(
            ["allocation_version_id", "project_id"],
            [
                "unit_economics_allocation_versions.id",
                "unit_economics_allocation_versions.project_id",
            ],
            name="version",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["area_type_id", "project_id"],
            ["area_types.id", "area_types.project_id"],
            name="area_type",
            ondelete="RESTRICT",
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
            name=op.f("fk_unit_economics_cost_pools_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["phase_id", "project_id"],
            ["phases.id", "phases.project_id"],
            name="phase",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_unit_economics_cost_pools")),
        sa.UniqueConstraint("allocation_version_id", "pool_number", name="uq_ue_pool_number"),
        sa.UniqueConstraint("id", "project_id", name="ue_pool_project"),
        sa.UniqueConstraint(
            "id", "allocation_version_id", "project_id", name="ue_pool_version_project"
        ),
    )
    op.create_index(
        "ix_ue_pools_version", "unit_economics_cost_pools", ["allocation_version_id"], unique=False
    )
    # One canonical land pool per version. Two of them each draw the whole
    # project land total, so the land cost doubles and every pool still
    # reconciles — the failure mode nothing downstream can detect.
    op.create_index(
        "uq_ue_pools_one_project_land",
        "unit_economics_cost_pools",
        ["allocation_version_id"],
        unique=True,
        postgresql_where=sa.text("source_kind = 'project_land'"),
    )
    op.create_table(
        "unit_economics_allocations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("allocation_version_id", sa.UUID(), nullable=False),
        sa.Column("cost_pool_id", sa.UUID(), nullable=False),
        sa.Column("unit_id", sa.UUID(), nullable=False),
        sa.Column("driver_value", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("driver_share", sa.Numeric(precision=9, scale=6), nullable=False),
        sa.Column("allocated_amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("source_area_schedule_id", sa.UUID(), nullable=True),
        sa.Column("source_price_version_id", sa.UUID(), nullable=True),
        sa.Column("is_rounding_recipient", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "driver_share >= 0", name=op.f("ck_unit_economics_allocations_share_nonneg")
        ),
        sa.CheckConstraint(
            "driver_value >= 0", name=op.f("ck_unit_economics_allocations_driver_nonneg")
        ),
        sa.ForeignKeyConstraint(
            ["allocation_version_id", "project_id"],
            [
                "unit_economics_allocation_versions.id",
                "unit_economics_allocation_versions.project_id",
            ],
            name="version",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["cost_pool_id", "allocation_version_id", "project_id"],
            [
                "unit_economics_cost_pools.id",
                "unit_economics_cost_pools.allocation_version_id",
                "unit_economics_cost_pools.project_id",
            ],
            name="pool",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_area_schedule_id", "project_id"],
            ["unit_area_schedules.id", "unit_area_schedules.project_id"],
            name="schedule",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_price_version_id", "project_id"],
            ["unit_price_versions.id", "unit_price_versions.project_id"],
            name="price_version",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["unit_id", "project_id"],
            ["units.id", "units.project_id"],
            name="unit",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_unit_economics_allocations")),
        sa.UniqueConstraint("cost_pool_id", "unit_id", name="uq_ue_allocation_unit"),
    )
    op.create_index(
        "ix_ue_allocations_pool", "unit_economics_allocations", ["cost_pool_id"], unique=False
    )
    op.create_index(
        "ix_ue_allocations_version_unit",
        "unit_economics_allocations",
        ["allocation_version_id", "unit_id"],
        unique=False,
    )
    op.create_table(
        "unit_economics_unit_costs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("unit_id", sa.UUID(), nullable=False),
        sa.Column("sale_contract_id", sa.UUID(), nullable=True),
        sa.Column("currency_id", sa.UUID(), nullable=False),
        sa.Column("cost_type", sa.String(length=32), nullable=False),
        sa.Column("basis", sa.String(length=16), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("reference", sa.String(length=200), nullable=True),
        sa.Column("notes", sa.String(length=2000), nullable=True),
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
        sa.Column("reversal_reason", sa.String(length=1000), nullable=True),
        sa.CheckConstraint(
            "basis IN ('forecast', 'actual')", name=op.f("ck_unit_economics_unit_costs_basis_ok")
        ),
        sa.CheckConstraint(
            "cost_type IN ('unit_upgrade', 'finishes', 'furniture_appliance', "
            "'legal_registry_support', 'rectification', 'other_direct', 'marketing', "
            "'sales_commission', 'branch_commission', 'payment_fee', "
            "'seller_paid_legal', 'other_selling')",
            name=op.f("ck_unit_economics_unit_costs_type_ok"),
        ),
        sa.CheckConstraint(
            "status <> 'reversed' OR (reversed_at IS NOT NULL "
            "AND reversal_reason IS NOT NULL AND reversed_by_user_id IS NOT NULL)",
            name=op.f("ck_unit_economics_unit_costs_reversal_complete"),
        ),
        sa.CheckConstraint(
            "status IN ('active', 'reversed')", name=op.f("ck_unit_economics_unit_costs_status_ok")
        ),
        sa.CheckConstraint("amount > 0", name=op.f("ck_unit_economics_unit_costs_amount_positive")),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_unit_economics_unit_costs_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["currency_id"],
            ["currencies.id"],
            name=op.f("fk_unit_economics_unit_costs_currency_id_currencies"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reversed_by_user_id"],
            ["users.id"],
            name=op.f("fk_unit_economics_unit_costs_reversed_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["sale_contract_id", "project_id"],
            ["sale_contracts.id", "sale_contracts.project_id"],
            name="sale",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["unit_id", "project_id"],
            ["units.id", "units.project_id"],
            name="unit",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_unit_economics_unit_costs")),
    )
    op.create_index(
        "ix_ue_unit_costs_project_status",
        "unit_economics_unit_costs",
        ["project_id", "status"],
        unique=False,
    )
    op.create_index(
        "ix_ue_unit_costs_sale", "unit_economics_unit_costs", ["sale_contract_id"], unique=False
    )
    op.create_index(
        "ix_ue_unit_costs_unit_status",
        "unit_economics_unit_costs",
        ["unit_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    """Revert this revision."""
    op.drop_index("ix_ue_unit_costs_unit_status", table_name="unit_economics_unit_costs")
    op.drop_index("ix_ue_unit_costs_sale", table_name="unit_economics_unit_costs")
    op.drop_index("ix_ue_unit_costs_project_status", table_name="unit_economics_unit_costs")
    op.drop_table("unit_economics_unit_costs")
    op.drop_index("ix_ue_allocations_version_unit", table_name="unit_economics_allocations")
    op.drop_index("ix_ue_allocations_pool", table_name="unit_economics_allocations")
    op.drop_table("unit_economics_allocations")
    op.drop_index("uq_ue_pools_one_project_land", table_name="unit_economics_cost_pools")
    op.drop_index("ix_ue_pools_version", table_name="unit_economics_cost_pools")
    op.drop_table("unit_economics_cost_pools")
    # The self-referencing foreign key goes before the table it points at.
    op.drop_constraint("source_version", "unit_economics_allocation_versions", type_="foreignkey")
    op.drop_index(
        "uq_ue_versions_one_active",
        table_name="unit_economics_allocation_versions",
        postgresql_where=sa.text("status = 'active'"),
    )
    op.drop_index(
        op.f("ix_unit_economics_allocation_versions_project_id"),
        table_name="unit_economics_allocation_versions",
    )
    op.drop_index("ix_ue_versions_project_status", table_name="unit_economics_allocation_versions")
    op.drop_index(
        "ix_ue_versions_project_effective", table_name="unit_economics_allocation_versions"
    )
    op.drop_table("unit_economics_allocation_versions")
