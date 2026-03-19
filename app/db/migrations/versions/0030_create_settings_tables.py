"""create settings tables

Revision ID: 0030
Revises: 0029
Create Date: 2026-03-19

PR-S1 — Settings Business Domain

Introduces the three Settings-domain tables that form the governance
scaffolding for core platform business rules:

  settings_pricing_policies     — named pricing-behaviour defaults
  settings_commission_policies  — named commission-pool defaults
  settings_project_templates    — reusable project-setup bundles

All tables are standalone (no FK to project hierarchy), so this migration
is fully additive and non-breaking.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0030"
down_revision: Union[str, None] = "0029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # settings_pricing_policies
    # ------------------------------------------------------------------
    op.create_table(
        "settings_pricing_policies",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("currency", sa.String(10), nullable=False, server_default="AED"),
        sa.Column(
            "base_markup_percent",
            sa.Numeric(8, 4),
            nullable=False,
            server_default="0.0000",
        ),
        sa.Column(
            "balcony_price_factor",
            sa.Numeric(8, 4),
            nullable=False,
            server_default="0.0000",
        ),
        sa.Column(
            "parking_price_mode",
            sa.String(50),
            nullable=False,
            server_default="excluded",
        ),
        sa.Column(
            "storage_price_mode",
            sa.String(50),
            nullable=False,
            server_default="excluded",
        ),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_settings_pricing_policies_name",
        "settings_pricing_policies",
        ["name"],
    )
    op.create_index(
        "ix_settings_pricing_policies_is_default",
        "settings_pricing_policies",
        ["is_default"],
    )

    # ------------------------------------------------------------------
    # settings_commission_policies
    # ------------------------------------------------------------------
    op.create_table(
        "settings_commission_policies",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "pool_percent",
            sa.Numeric(8, 4),
            nullable=False,
            server_default="0.0000",
        ),
        sa.Column(
            "calculation_mode",
            sa.String(50),
            nullable=False,
            server_default="marginal",
        ),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_settings_commission_policies_name",
        "settings_commission_policies",
        ["name"],
    )
    op.create_index(
        "ix_settings_commission_policies_is_default",
        "settings_commission_policies",
        ["is_default"],
    )

    # ------------------------------------------------------------------
    # settings_project_templates
    # ------------------------------------------------------------------
    op.create_table(
        "settings_project_templates",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "default_pricing_policy_id",
            sa.String(36),
            sa.ForeignKey(
                "settings_pricing_policies.id", ondelete="SET NULL"
            ),
            nullable=True,
        ),
        sa.Column(
            "default_commission_policy_id",
            sa.String(36),
            sa.ForeignKey(
                "settings_commission_policies.id", ondelete="SET NULL"
            ),
            nullable=True,
        ),
        sa.Column(
            "default_currency", sa.String(10), nullable=False, server_default="AED"
        ),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_settings_project_templates_name",
        "settings_project_templates",
        ["name"],
    )
    op.create_index(
        "ix_settings_project_templates_default_pricing_policy_id",
        "settings_project_templates",
        ["default_pricing_policy_id"],
    )
    op.create_index(
        "ix_settings_project_templates_default_commission_policy_id",
        "settings_project_templates",
        ["default_commission_policy_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_settings_project_templates_default_commission_policy_id",
        table_name="settings_project_templates",
    )
    op.drop_index(
        "ix_settings_project_templates_default_pricing_policy_id",
        table_name="settings_project_templates",
    )
    op.drop_index(
        "ix_settings_project_templates_name",
        table_name="settings_project_templates",
    )
    op.drop_table("settings_project_templates")

    op.drop_index(
        "ix_settings_commission_policies_is_default",
        table_name="settings_commission_policies",
    )
    op.drop_index(
        "ix_settings_commission_policies_name",
        table_name="settings_commission_policies",
    )
    op.drop_table("settings_commission_policies")

    op.drop_index(
        "ix_settings_pricing_policies_is_default",
        table_name="settings_pricing_policies",
    )
    op.drop_index(
        "ix_settings_pricing_policies_name",
        table_name="settings_pricing_policies",
    )
    op.drop_table("settings_pricing_policies")
