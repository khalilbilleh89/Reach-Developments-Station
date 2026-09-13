"""Retain owner-removed units and their linked commercial history."""

import sqlalchemy as sa
from alembic import op

revision = "0030_unit_removal"
down_revision = "0029_merge_installment_tax"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("units", sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    if op.get_bind().scalar(
        sa.text("SELECT EXISTS (SELECT 1 FROM units WHERE removed_at IS NOT NULL)")
    ):
        raise RuntimeError("Removed unit history exists; retain this schema and roll forward.")
    op.drop_column("units", "removed_at")
