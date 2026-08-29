"""Inventory, phases and configurable fields.

Creates the physical product catalogue: phase, building, floor, unit, the areas
a unit is measured by, the sub-assets that belong to it, and the constrained
custom-field metadata that extends project, parcel and unit records.

Two corrections travel with it, both to model/schema differences PR-MVP-02
surfaced and deliberately left alone:

* ``ck_country_approval_thresholds_discount_review_amount_non_negative`` renders
  65 characters, past PostgreSQL's 63-character identifier limit, so the
  deployed database holds a hashed truncation the metadata could never match.
  It is renamed — not dropped and rebuilt — so the existing rows are not
  re-validated and the constraint's identity is preserved.
* ``user_roles`` declared a ``UniqueConstraint`` over the columns its composite
  primary key already covered. PostgreSQL kept only the primary key, so the
  constraint never existed in any database; the fix is in the model and needs no
  operation here.

``user_project_access`` gains ``phase_scope``. Every existing row defaults to
``all``, which is exactly what those memberships have always meant.

Revision ID: 0003_inventory
Revises: 0002_project_land_permits
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_inventory"
down_revision: str | Sequence[str] | None = "0002_project_land_permits"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply this revision."""
    op.create_table(
        "area_types",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("area_role", sa.String(length=32), nullable=False),
        sa.Column("unit_of_measure", sa.String(length=16), nullable=False),
        sa.Column("weight_factor", sa.Numeric(precision=9, scale=6), nullable=False),
        sa.Column("required_for_release", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
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
            "area_role IN ('internal', 'outdoor', 'ancillary', 'plot', 'gross', 'other')",
            name=op.f("ck_area_types_role_allowed"),
        ),
        sa.CheckConstraint("code = upper(code)", name=op.f("ck_area_types_code_upper")),
        sa.CheckConstraint("length(code) > 0", name=op.f("ck_area_types_code_not_blank")),
        sa.CheckConstraint(
            "weight_factor >= 0 AND weight_factor <= 1", name=op.f("ck_area_types_factor_range")
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_area_types_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_area_types_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_area_types")),
        sa.UniqueConstraint("id", "project_id", name="area_type_project"),
        sa.UniqueConstraint("project_id", "code", name=op.f("uq_area_types_project_id_code")),
    )
    op.create_index(
        "uq_area_types_one_internal",
        "area_types",
        ["project_id"],
        unique=True,
        postgresql_where=sa.text("area_role = 'internal' AND is_active"),
    )
    op.create_table(
        "custom_field_definitions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("field_key", sa.String(length=64), nullable=False),
        sa.Column("display_label", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("data_type", sa.String(length=16), nullable=False),
        sa.Column("unit_of_measure", sa.String(length=32), nullable=True),
        sa.Column("help_text", sa.String(length=500), nullable=True),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("required_for_release", sa.Boolean(), nullable=False),
        sa.Column("minimum_value", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("maximum_value", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("regex_pattern", sa.String(length=200), nullable=True),
        sa.Column("is_unique", sa.Boolean(), nullable=False),
        sa.Column("scope_type", sa.String(length=16), nullable=False),
        sa.Column("country_pack_id", sa.UUID(), nullable=True),
        sa.Column("project_id", sa.UUID(), nullable=True),
        sa.Column("unit_type_code", sa.String(length=64), nullable=True),
        sa.Column("visible_role_keys", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("editable_role_keys", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("sensitive", sa.Boolean(), nullable=False),
        sa.Column("approval_required", sa.Boolean(), nullable=False),
        sa.Column("filterable", sa.Boolean(), nullable=False),
        sa.Column("groupable", sa.Boolean(), nullable=False),
        sa.Column("dashboard_visible", sa.Boolean(), nullable=False),
        sa.Column("export_visible", sa.Boolean(), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("change_reason", sa.String(length=500), nullable=True),
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.Column("updated_by_user_id", sa.UUID(), nullable=True),
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
            "(scope_type = 'global' AND country_pack_id IS NULL AND project_id IS NULL "
            "AND unit_type_code IS NULL) "
            "OR (scope_type = 'country' AND country_pack_id IS NOT NULL "
            "AND project_id IS NULL AND unit_type_code IS NULL) "
            "OR (scope_type = 'project' AND project_id IS NOT NULL "
            "AND country_pack_id IS NULL AND unit_type_code IS NULL) "
            "OR (scope_type = 'unit_type' AND project_id IS NOT NULL "
            "AND unit_type_code IS NOT NULL AND country_pack_id IS NULL)",
            name=op.f("ck_custom_field_definitions_scope_columns"),
        ),
        sa.CheckConstraint(
            "data_type IN ('text', 'integer', 'decimal', 'boolean', 'date', 'option')",
            name=op.f("ck_custom_field_definitions_type_allowed"),
        ),
        sa.CheckConstraint(
            "entity_type IN ('project', 'land_parcel', 'unit')",
            name=op.f("ck_custom_field_definitions_entity_allowed"),
        ),
        sa.CheckConstraint(
            "scope_type <> 'unit_type' OR entity_type = 'unit'",
            name=op.f("ck_custom_field_definitions_unit_type_scope_is_unit"),
        ),
        sa.CheckConstraint(
            "scope_type IN ('global', 'country', 'project', 'unit_type')",
            name=op.f("ck_custom_field_definitions_scope_allowed"),
        ),
        sa.CheckConstraint(
            "NOT sensitive OR visible_role_keys IS NOT NULL",
            name=op.f("ck_custom_field_definitions_sensitive_needs_roles"),
        ),
        sa.CheckConstraint(
            "field_key = lower(field_key)", name=op.f("ck_custom_field_definitions_key_lower")
        ),
        sa.CheckConstraint(
            "length(field_key) > 0", name=op.f("ck_custom_field_definitions_key_not_blank")
        ),
        sa.CheckConstraint(
            "minimum_value IS NULL OR maximum_value IS NULL OR maximum_value >= minimum_value",
            name=op.f("ck_custom_field_definitions_bounds_ordered"),
        ),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from",
            name=op.f("ck_custom_field_definitions_validity_ordered"),
        ),
        sa.CheckConstraint(
            "version >= 1", name=op.f("ck_custom_field_definitions_version_positive")
        ),
        sa.ForeignKeyConstraint(
            ["country_pack_id"],
            ["country_packs.id"],
            name=op.f("fk_custom_field_definitions_country_pack_id_country_packs"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_custom_field_definitions_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_custom_field_definitions_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"],
            ["users.id"],
            name=op.f("fk_custom_field_definitions_updated_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_custom_field_definitions")),
    )
    op.create_index(
        "ix_custom_field_definitions_entity_type_scope_type",
        "custom_field_definitions",
        ["entity_type", "scope_type"],
        unique=False,
    )
    op.create_index(
        "uq_custom_field_definitions_scope",
        "custom_field_definitions",
        [
            "entity_type",
            "field_key",
            "scope_type",
            "country_pack_id",
            "project_id",
            "unit_type_code",
        ],
        unique=True,
        postgresql_nulls_not_distinct=True,
        postgresql_where=sa.text("is_active"),
    )
    op.create_table(
        "phases",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("planned_start", sa.Date(), nullable=True),
        sa.Column("planned_completion", sa.Date(), nullable=True),
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
            "status IN ('planning', 'active', 'on_hold', 'completed', 'cancelled')",
            name=op.f("ck_phases_status_allowed"),
        ),
        sa.CheckConstraint("code = upper(code)", name=op.f("ck_phases_code_upper")),
        sa.CheckConstraint("length(code) > 0", name=op.f("ck_phases_code_not_blank")),
        sa.CheckConstraint("length(name) > 0", name=op.f("ck_phases_name_not_blank")),
        sa.CheckConstraint(
            "planned_completion IS NULL OR planned_start IS NULL "
            "OR planned_completion >= planned_start",
            name=op.f("ck_phases_dates_ordered"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_phases_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_phases_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_phases")),
        sa.UniqueConstraint("id", "project_id", name="phase_project"),
        sa.UniqueConstraint("project_id", "code", name=op.f("uq_phases_project_id_code")),
    )
    op.create_index("ix_phases_project_id_status", "phases", ["project_id", "status"], unique=False)
    op.create_table(
        "buildings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("phase_id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("zone", sa.String(length=120), nullable=True),
        sa.Column("block", sa.String(length=120), nullable=True),
        sa.Column("entrance_wing", sa.String(length=120), nullable=True),
        sa.Column("sequence", sa.Integer(), nullable=False),
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
        sa.CheckConstraint("code = upper(code)", name=op.f("ck_buildings_code_upper")),
        sa.CheckConstraint("length(code) > 0", name=op.f("ck_buildings_code_not_blank")),
        sa.CheckConstraint("length(name) > 0", name=op.f("ck_buildings_name_not_blank")),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_buildings_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["phase_id", "project_id"],
            ["phases.id", "phases.project_id"],
            name="phase",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_buildings")),
        sa.UniqueConstraint("id", "project_id", name="building_project"),
        sa.UniqueConstraint("phase_id", "code", name=op.f("uq_buildings_phase_id_code")),
    )
    op.create_index("ix_buildings_phase_id", "buildings", ["phase_id"], unique=False)
    op.create_table(
        "custom_field_options",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("definition_id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.CheckConstraint("length(code) > 0", name=op.f("ck_custom_field_options_code_not_blank")),
        sa.ForeignKeyConstraint(
            ["definition_id"],
            ["custom_field_definitions.id"],
            name=op.f("fk_custom_field_options_definition_id_custom_field_definitions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_custom_field_options")),
        sa.UniqueConstraint(
            "definition_id", "code", name=op.f("uq_custom_field_options_definition_id_code")
        ),
    )
    op.create_table(
        "land_parcel_custom_field_values",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("definition_id", sa.UUID(), nullable=False),
        sa.Column("parcel_id", sa.UUID(), nullable=False),
        sa.Column("value_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("unique_value", sa.String(length=200), nullable=True),
        sa.Column("updated_by_user_id", sa.UUID(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["definition_id"],
            ["custom_field_definitions.id"],
            name=op.f("fk_land_parcel_custom_field_values_definition_id_custom_field_definitions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["parcel_id"],
            ["land_parcels.id"],
            name=op.f("fk_land_parcel_custom_field_values_parcel_id_land_parcels"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"],
            ["users.id"],
            name=op.f("fk_land_parcel_custom_field_values_updated_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_land_parcel_custom_field_values")),
        sa.UniqueConstraint(
            "definition_id",
            "parcel_id",
            name=op.f("uq_land_parcel_custom_field_values_definition_id_parcel_id"),
        ),
    )
    op.create_index(
        "uq_land_parcel_custom_field_values_unique_value",
        "land_parcel_custom_field_values",
        ["definition_id", "unique_value"],
        unique=True,
        postgresql_where=sa.text("unique_value IS NOT NULL"),
    )
    op.create_table(
        "project_custom_field_values",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("definition_id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("value_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("unique_value", sa.String(length=200), nullable=True),
        sa.Column("updated_by_user_id", sa.UUID(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["definition_id"],
            ["custom_field_definitions.id"],
            name=op.f("fk_project_custom_field_values_definition_id_custom_field_definitions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_project_custom_field_values_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"],
            ["users.id"],
            name=op.f("fk_project_custom_field_values_updated_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_project_custom_field_values")),
        sa.UniqueConstraint(
            "definition_id",
            "project_id",
            name=op.f("uq_project_custom_field_values_definition_id_project_id"),
        ),
    )
    op.create_index(
        "uq_project_custom_field_values_unique_value",
        "project_custom_field_values",
        ["definition_id", "unique_value"],
        unique=True,
        postgresql_where=sa.text("unique_value IS NOT NULL"),
    )
    op.create_table(
        "user_phase_access",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("phase_id", sa.UUID(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("granted_by_user_id", sa.UUID(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by_user_id", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(
            ["granted_by_user_id"],
            ["users.id"],
            name=op.f("fk_user_phase_access_granted_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["phase_id", "project_id"],
            ["phases.id", "phases.project_id"],
            name="phase",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id", "user_id"],
            ["user_project_access.project_id", "user_project_access.user_id"],
            name="membership",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["revoked_by_user_id"],
            ["users.id"],
            name=op.f("fk_user_phase_access_revoked_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_phase_access")),
        sa.UniqueConstraint(
            "user_id", "phase_id", name=op.f("uq_user_phase_access_user_id_phase_id")
        ),
    )
    op.create_index("ix_user_phase_access_user_id", "user_phase_access", ["user_id"], unique=False)
    op.create_table(
        "floors",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("building_id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("level_number", sa.Integer(), nullable=True),
        sa.Column("sequence", sa.Integer(), nullable=False),
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
        sa.CheckConstraint("code = upper(code)", name=op.f("ck_floors_code_upper")),
        sa.CheckConstraint("length(code) > 0", name=op.f("ck_floors_code_not_blank")),
        sa.CheckConstraint("length(label) > 0", name=op.f("ck_floors_label_not_blank")),
        sa.ForeignKeyConstraint(
            ["building_id", "project_id"],
            ["buildings.id", "buildings.project_id"],
            name="building",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_floors_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_floors")),
        sa.UniqueConstraint("building_id", "code", name=op.f("uq_floors_building_id_code")),
        sa.UniqueConstraint("id", "project_id", name="floor_project"),
    )
    op.create_index("ix_floors_building_id", "floors", ["building_id"], unique=False)
    op.create_table(
        "units",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("floor_id", sa.UUID(), nullable=False),
        sa.Column("unit_number", sa.String(length=32), nullable=False),
        sa.Column("unit_reference", sa.String(length=64), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("asset_class", sa.String(length=32), nullable=False),
        sa.Column("unit_type_code", sa.String(length=64), nullable=True),
        sa.Column("bedrooms", sa.Integer(), nullable=True),
        sa.Column("bathrooms", sa.Integer(), nullable=True),
        sa.Column("has_maid_room", sa.Boolean(), nullable=False),
        sa.Column("is_duplex", sa.Boolean(), nullable=False),
        sa.Column("is_penthouse", sa.Boolean(), nullable=False),
        sa.Column("furnishing_specification_code", sa.String(length=64), nullable=True),
        sa.Column("floor_band_code", sa.String(length=64), nullable=True),
        sa.Column("orientation_code", sa.String(length=64), nullable=True),
        sa.Column("view_class_code", sa.String(length=64), nullable=True),
        sa.Column("is_corner", sa.Boolean(), nullable=False),
        sa.Column("pool_access", sa.Boolean(), nullable=False),
        sa.Column("accessibility_code", sa.String(length=64), nullable=True),
        sa.Column("garden_class_code", sa.String(length=64), nullable=True),
        sa.Column("plot_coverage_fraction", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("commercial_status", sa.String(length=32), nullable=False),
        sa.Column("legal_status", sa.String(length=32), nullable=False),
        sa.Column("collection_status", sa.String(length=32), nullable=False),
        sa.Column("delivery_status", sa.String(length=32), nullable=False),
        sa.Column("drawings_approved", sa.Boolean(), nullable=False),
        sa.Column("legal_sale_eligible", sa.Boolean(), nullable=False),
        sa.Column("pricing_approved", sa.Boolean(), nullable=False),
        sa.Column("release_date", sa.Date(), nullable=True),
        sa.Column("release_batch", sa.String(length=64), nullable=True),
        sa.Column("block_reason", sa.String(length=500), nullable=True),
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
            "asset_class IN ('apartment', 'villa', 'townhouse', 'commercial', 'other')",
            name=op.f("ck_units_asset_class_allowed"),
        ),
        sa.CheckConstraint(
            "collection_status IN ('not_started', 'current', 'partially_paid', "
            "'overdue', 'disputed', 'cleared', 'cancelled')",
            name=op.f("ck_units_collection_ok"),
        ),
        sa.CheckConstraint(
            "commercial_status IN ('unreleased', 'available', 'held', 'reserved', "
            "'contracted', 'cancelled', 'returned')",
            name=op.f("ck_units_commercial_ok"),
        ),
        sa.CheckConstraint(
            "delivery_status IN ('not_started', 'under_construction', 'ready', "
            "'handover_blocked', 'handover_ready', 'handed_over')",
            name=op.f("ck_units_delivery_ok"),
        ),
        sa.CheckConstraint(
            "legal_status IN ('not_started', 'eligible', 'spa_in_progress', "
            "'spa_signed', 'registration_in_progress', 'registered', "
            "'title_transferred', 'cancelled')",
            name=op.f("ck_units_legal_ok"),
        ),
        sa.CheckConstraint(
            "bathrooms IS NULL OR bathrooms >= 0", name=op.f("ck_units_bathrooms_nonneg")
        ),
        sa.CheckConstraint(
            "bedrooms IS NULL OR bedrooms >= 0", name=op.f("ck_units_bedrooms_nonneg")
        ),
        sa.CheckConstraint("length(unit_number) > 0", name=op.f("ck_units_number_not_blank")),
        sa.CheckConstraint("length(unit_reference) > 0", name=op.f("ck_units_reference_not_blank")),
        sa.CheckConstraint(
            "plot_coverage_fraction IS NULL "
            "OR (plot_coverage_fraction >= 0 AND plot_coverage_fraction <= 1)",
            name=op.f("ck_units_coverage_range"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_units_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["floor_id", "project_id"],
            ["floors.id", "floors.project_id"],
            name="floor",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_units")),
        sa.UniqueConstraint("floor_id", "unit_number", name=op.f("uq_units_floor_id_unit_number")),
        sa.UniqueConstraint("id", "project_id", name="unit_project"),
        sa.UniqueConstraint(
            "project_id", "unit_reference", name=op.f("uq_units_project_id_unit_reference")
        ),
    )
    op.create_index("ix_units_floor_id", "units", ["floor_id"], unique=False)
    op.create_index(
        "ix_units_project_id_commercial_status",
        "units",
        ["project_id", "commercial_status"],
        unique=False,
    )
    op.create_index(
        "ix_units_project_id_unit_type_code",
        "units",
        ["project_id", "unit_type_code"],
        unique=False,
    )
    op.create_table(
        "inventory_sub_assets",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("floor_id", sa.UUID(), nullable=True),
        sa.Column("linked_unit_id", sa.UUID(), nullable=True),
        sa.Column("asset_reference", sa.String(length=64), nullable=False),
        sa.Column("asset_type", sa.String(length=32), nullable=False),
        sa.Column("subtype_code", sa.String(length=64), nullable=True),
        sa.Column("area", sa.Numeric(precision=18, scale=4), nullable=True),
        sa.Column("transfer_mode", sa.String(length=16), nullable=False),
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
            "asset_type IN ('parking', 'storage', 'other')",
            name=op.f("ck_inventory_sub_assets_type_allowed"),
        ),
        sa.CheckConstraint(
            "transfer_mode IN ('attached', 'independent')",
            name=op.f("ck_inventory_sub_assets_transfer_allowed"),
        ),
        sa.CheckConstraint(
            "area IS NULL OR area >= 0", name=op.f("ck_inventory_sub_assets_area_nonneg")
        ),
        sa.CheckConstraint(
            "length(asset_reference) > 0", name=op.f("ck_inventory_sub_assets_reference_not_blank")
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_inventory_sub_assets_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["floor_id", "project_id"],
            ["floors.id", "floors.project_id"],
            name="floor",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["linked_unit_id", "project_id"],
            ["units.id", "units.project_id"],
            name="unit",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_inventory_sub_assets_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_inventory_sub_assets")),
        sa.UniqueConstraint(
            "project_id",
            "asset_reference",
            name=op.f("uq_inventory_sub_assets_project_id_asset_reference"),
        ),
    )
    op.create_index(
        "ix_inventory_sub_assets_linked_unit_id_asset_type",
        "inventory_sub_assets",
        ["linked_unit_id", "asset_type"],
        unique=False,
    )
    op.create_table(
        "unit_area_schedules",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("unit_id", sa.UUID(), nullable=False),
        sa.Column("revision_code", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("measurement_standard", sa.String(length=120), nullable=True),
        sa.Column("plan_revision", sa.String(length=64), nullable=True),
        sa.Column("source", sa.String(length=120), nullable=True),
        sa.Column("measured_date", sa.Date(), nullable=True),
        sa.Column("verified_by_user_id", sa.UUID(), nullable=True),
        sa.Column("approved_by_user_id", sa.UUID(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reconciled", sa.Boolean(), nullable=False),
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
            "(status <> 'approved') OR "
            "(approved_by_user_id IS NOT NULL AND approved_at IS NOT NULL AND reconciled)",
            name=op.f("ck_unit_area_schedules_approved_complete"),
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'approved', 'superseded')",
            name=op.f("ck_unit_area_schedules_status_allowed"),
        ),
        sa.CheckConstraint(
            "length(revision_code) > 0", name=op.f("ck_unit_area_schedules_revision_not_blank")
        ),
        sa.ForeignKeyConstraint(
            ["approved_by_user_id"],
            ["users.id"],
            name=op.f("fk_unit_area_schedules_approved_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_unit_area_schedules_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["unit_id", "project_id"],
            ["units.id", "units.project_id"],
            name="unit",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["verified_by_user_id"],
            ["users.id"],
            name=op.f("fk_unit_area_schedules_verified_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_unit_area_schedules")),
        sa.UniqueConstraint("id", "project_id", name="schedule_project"),
        sa.UniqueConstraint(
            "unit_id", "revision_code", name=op.f("uq_unit_area_schedules_unit_id_revision_code")
        ),
    )
    op.create_index(
        "ix_unit_area_schedules_unit_id_status",
        "unit_area_schedules",
        ["unit_id", "status"],
        unique=False,
    )
    op.create_index(
        "uq_unit_area_schedules_current",
        "unit_area_schedules",
        ["unit_id"],
        unique=True,
        postgresql_where=sa.text("status = 'approved'"),
    )
    op.create_table(
        "unit_custom_field_values",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("definition_id", sa.UUID(), nullable=False),
        sa.Column("unit_id", sa.UUID(), nullable=False),
        sa.Column("value_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("unique_value", sa.String(length=200), nullable=True),
        sa.Column("updated_by_user_id", sa.UUID(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["definition_id"],
            ["custom_field_definitions.id"],
            name=op.f("fk_unit_custom_field_values_definition_id_custom_field_definitions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["unit_id"],
            ["units.id"],
            name=op.f("fk_unit_custom_field_values_unit_id_units"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"],
            ["users.id"],
            name=op.f("fk_unit_custom_field_values_updated_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_unit_custom_field_values")),
        sa.UniqueConstraint(
            "definition_id",
            "unit_id",
            name=op.f("uq_unit_custom_field_values_definition_id_unit_id"),
        ),
    )
    op.create_index(
        "uq_unit_custom_field_values_unique_value",
        "unit_custom_field_values",
        ["definition_id", "unique_value"],
        unique=True,
        postgresql_where=sa.text("unique_value IS NOT NULL"),
    )
    op.create_table(
        "unit_status_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("unit_id", sa.UUID(), nullable=False),
        sa.Column("dimension", sa.String(length=16), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=False),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("notes", sa.String(length=2000), nullable=True),
        sa.Column("changed_by_user_id", sa.UUID(), nullable=False),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "dimension IN ('commercial', 'legal', 'collection', 'delivery')",
            name=op.f("ck_unit_status_events_dimension_allowed"),
        ),
        sa.CheckConstraint(
            "from_status <> to_status", name=op.f("ck_unit_status_events_status_changed")
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_user_id"],
            ["users.id"],
            name=op.f("fk_unit_status_events_changed_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["unit_id"],
            ["units.id"],
            name=op.f("fk_unit_status_events_unit_id_units"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_unit_status_events")),
    )
    op.create_index(
        "ix_unit_status_events_unit_id_dimension",
        "unit_status_events",
        ["unit_id", "dimension"],
        unique=False,
    )
    op.create_table(
        "unit_area_values",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("unit_area_schedule_id", sa.UUID(), nullable=False),
        sa.Column("area_type_id", sa.UUID(), nullable=False),
        sa.Column("raw_area", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.CheckConstraint("raw_area >= 0", name=op.f("ck_unit_area_values_area_nonneg")),
        sa.ForeignKeyConstraint(
            ["area_type_id", "project_id"],
            ["area_types.id", "area_types.project_id"],
            name="area_type",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["unit_area_schedule_id", "project_id"],
            ["unit_area_schedules.id", "unit_area_schedules.project_id"],
            name="schedule",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_unit_area_values")),
        sa.UniqueConstraint(
            "unit_area_schedule_id",
            "area_type_id",
            name=op.f("uq_unit_area_values_unit_area_schedule_id_area_type_id"),
        ),
    )
    # A rename, not a drop and rebuild: the rule is unchanged, so re-validating
    # every row would be work done to reach the same answer. The old name is the
    # hashed truncation PostgreSQL actually holds, read from pg_constraint.
    op.execute(
        "ALTER TABLE country_approval_thresholds "
        "RENAME CONSTRAINT ck_country_approval_thresholds_discount_review_amount_n_9f00 "
        "TO ck_country_approval_thresholds_discount_amount_nonneg"
    )
    op.add_column(
        "user_project_access",
        sa.Column("phase_scope", sa.String(length=16), server_default="all", nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_user_project_access_phase_scope_allowed"),
        "user_project_access",
        "phase_scope IN ('all', 'selected')",
    )


def downgrade() -> None:
    """Revert this revision."""
    op.drop_constraint(
        op.f("ck_user_project_access_phase_scope_allowed"), "user_project_access", type_="check"
    )
    op.drop_column("user_project_access", "phase_scope")
    op.execute(
        "ALTER TABLE country_approval_thresholds "
        "RENAME CONSTRAINT ck_country_approval_thresholds_discount_amount_nonneg "
        "TO ck_country_approval_thresholds_discount_review_amount_n_9f00"
    )
    op.drop_table("unit_area_values")
    op.drop_index("ix_unit_status_events_unit_id_dimension", table_name="unit_status_events")
    op.drop_table("unit_status_events")
    op.drop_index(
        "uq_unit_custom_field_values_unique_value",
        table_name="unit_custom_field_values",
        postgresql_where=sa.text("unique_value IS NOT NULL"),
    )
    op.drop_table("unit_custom_field_values")
    op.drop_index(
        "uq_unit_area_schedules_current",
        table_name="unit_area_schedules",
        postgresql_where=sa.text("status = 'approved'"),
    )
    op.drop_index("ix_unit_area_schedules_unit_id_status", table_name="unit_area_schedules")
    op.drop_table("unit_area_schedules")
    op.drop_index(
        "ix_inventory_sub_assets_linked_unit_id_asset_type", table_name="inventory_sub_assets"
    )
    op.drop_table("inventory_sub_assets")
    op.drop_index("ix_units_project_id_unit_type_code", table_name="units")
    op.drop_index("ix_units_project_id_commercial_status", table_name="units")
    op.drop_index("ix_units_floor_id", table_name="units")
    op.drop_table("units")
    op.drop_index("ix_floors_building_id", table_name="floors")
    op.drop_table("floors")
    op.drop_index("ix_user_phase_access_user_id", table_name="user_phase_access")
    op.drop_table("user_phase_access")
    op.drop_index(
        "uq_project_custom_field_values_unique_value",
        table_name="project_custom_field_values",
        postgresql_where=sa.text("unique_value IS NOT NULL"),
    )
    op.drop_table("project_custom_field_values")
    op.drop_index(
        "uq_land_parcel_custom_field_values_unique_value",
        table_name="land_parcel_custom_field_values",
        postgresql_where=sa.text("unique_value IS NOT NULL"),
    )
    op.drop_table("land_parcel_custom_field_values")
    op.drop_table("custom_field_options")
    op.drop_index("ix_buildings_phase_id", table_name="buildings")
    op.drop_table("buildings")
    op.drop_index("ix_phases_project_id_status", table_name="phases")
    op.drop_table("phases")
    op.drop_index(
        "uq_custom_field_definitions_scope",
        table_name="custom_field_definitions",
        postgresql_nulls_not_distinct=True,
        postgresql_where=sa.text("is_active"),
    )
    op.drop_index(
        "ix_custom_field_definitions_entity_type_scope_type", table_name="custom_field_definitions"
    )
    op.drop_table("custom_field_definitions")
    op.drop_index(
        "uq_area_types_one_internal",
        table_name="area_types",
        postgresql_where=sa.text("area_role = 'internal' AND is_active"),
    )
    op.drop_table("area_types")
