"""Allow units to belong directly to buildings without floors."""

import sqlalchemy as sa
from alembic import op

revision = "0031_building_units"
down_revision = "0030_unit_removal"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("units", sa.Column("building_id", sa.Uuid(), nullable=True))
    op.alter_column("units", "floor_id", nullable=True)
    op.create_foreign_key(
        "building",
        "units",
        "buildings",
        ["building_id", "project_id"],
        ["id", "project_id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        op.f("ck_units_one_parent"), "units", "(floor_id IS NULL) <> (building_id IS NULL)"
    )
    op.create_unique_constraint(
        "uq_units_building_id_unit_number", "units", ["building_id", "unit_number"]
    )


def downgrade() -> None:
    if op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT 1 FROM units WHERE floor_id IS NULL)")):
        raise RuntimeError(
            "Assign building-level units to real floors before downgrading; "
            "no unit is deleted or assigned an invented floor."
        )
    op.drop_constraint("uq_units_building_id_unit_number", "units", type_="unique")
    op.drop_constraint(op.f("ck_units_one_parent"), "units", type_="check")
    op.drop_constraint("building", "units", type_="foreignkey")
    op.alter_column("units", "floor_id", nullable=False)
    op.drop_column("units", "building_id")
