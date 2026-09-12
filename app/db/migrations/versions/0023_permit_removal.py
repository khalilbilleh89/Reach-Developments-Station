"""Retain removed permits while excluding them from active registers.

Revision ID: 0023_permit_removal
Revises: 0022_land_analytics
"""

import sqlalchemy as sa
from alembic import op

revision = "0023_permit_removal"
down_revision = "0022_land_analytics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("permits", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.drop_constraint(op.f("uq_permits_project_id_permit_code"), "permits", type_="unique")
    op.create_index(
        "uq_permits_project_id_permit_code",
        "permits",
        ["project_id", "permit_code"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    # Do not silently erase retained history to make an old uniqueness rule fit.
    if op.get_bind().scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM permits GROUP BY project_id, permit_code "
            "HAVING count(*) > 1)"
        )
    ):
        raise RuntimeError(
            "Cannot downgrade: permit codes were reused after removal. "
            "Preserve/export history and resolve duplicate codes first."
        )
    op.drop_index("uq_permits_project_id_permit_code", table_name="permits")
    op.create_unique_constraint(
        op.f("uq_permits_project_id_permit_code"), "permits", ["project_id", "permit_code"]
    )
    op.drop_column("permits", "deleted_at")
