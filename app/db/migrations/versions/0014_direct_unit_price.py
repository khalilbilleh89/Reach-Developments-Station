"""Allow directly entered unit prices without fabricating pricing configuration.

Existing prices keep their configuration. Rollback refuses while direct prices
exist because inventing a configuration or deleting approved history is unsafe.
"""

import sqlalchemy as sa
from alembic import op

revision = "0014_direct_unit_price"
down_revision = "0013_unit_master"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("unit_price_versions", "pricing_configuration_id", nullable=True)
    op.create_check_constraint(
        "direct_entry_basis",
        "unit_price_versions",
        "pricing_configuration_id IS NOT NULL OR "
        "(basis_snapshot_json ->> 'entry_method') IS NOT DISTINCT FROM 'direct'",
    )


def downgrade() -> None:
    if op.get_bind().scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM unit_price_versions "
            "WHERE pricing_configuration_id IS NULL)"
        )
    ):
        raise RuntimeError(
            "Direct price history exists. Restore a pre-upgrade backup or retain this schema; "
            "do not delete price history to downgrade."
        )
    op.drop_constraint(
        op.f("ck_unit_price_versions_direct_entry_basis"), "unit_price_versions", type_="check"
    )
    op.alter_column("unit_price_versions", "pricing_configuration_id", nullable=False)
