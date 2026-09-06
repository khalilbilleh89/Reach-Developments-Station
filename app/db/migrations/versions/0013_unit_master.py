"""Physical area components, unit features and unit document references.

Existing internal roles are unambiguous. Outdoor labels are deliberately not
guessed: project configuration assigns each to a physical component explicitly.
Downgrade removes the new annotations; export them before rolling back.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0013_unit_master"
down_revision = "0012_land_classification_text"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("area_types", sa.Column("physical_component", sa.String(24), nullable=True))
    op.execute("UPDATE area_types SET physical_component = 'internal' WHERE area_role = 'internal'")
    op.create_check_constraint(
        "component_allowed",
        "area_types",
        "physical_component IN ('internal', 'balcony', 'roof_garden', "
        "'front_garden', 'terrace', 'porches')",
    )
    op.create_check_constraint(
        "component_role",
        "area_types",
        "physical_component IS NULL OR (physical_component = 'internal' "
        "AND area_role = 'internal') OR (physical_component <> 'internal' "
        "AND area_role = 'outdoor')",
    )
    op.create_index(
        "uq_area_types_physical_component",
        "area_types",
        ["project_id", "physical_component"],
        unique=True,
        postgresql_where=sa.text("physical_component IS NOT NULL AND is_active"),
    )
    for table, fields, check in (
        (
            "unit_features",
            [sa.Column("label", sa.String(200), nullable=False)],
            "length(trim(label)) > 0",
        ),
        (
            "unit_documents",
            [
                sa.Column("title", sa.String(200), nullable=False),
                sa.Column("url", sa.String(2000), nullable=False),
                sa.Column("revision", sa.String(64), nullable=True),
            ],
            "length(trim(title)) > 0",
        ),
    ):
        op.create_table(
            table,
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("unit_id", postgresql.UUID(as_uuid=True), nullable=False),
            *fields,
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(
                ["unit_id", "project_id"], ["units.id", "units.project_id"], ondelete="RESTRICT"
            ),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
            sa.CheckConstraint(check, name="label_not_blank"),
        )
        op.create_index(f"ix_{table}_unit_id", table, ["unit_id"])


def downgrade() -> None:
    op.drop_table("unit_documents")
    op.drop_table("unit_features")
    op.drop_index("uq_area_types_physical_component", table_name="area_types")
    op.drop_constraint(op.f("ck_area_types_component_role"), "area_types", type_="check")
    op.drop_constraint(op.f("ck_area_types_component_allowed"), "area_types", type_="check")
    op.drop_column("area_types", "physical_component")
