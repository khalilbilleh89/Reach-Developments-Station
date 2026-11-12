"""Separate utility network availability, connection and next action."""

import sqlalchemy as sa
from alembic import op

revision = "0073_parcel_utilities"
down_revision = "0072_company_document_metadata"
branch_labels = None
depends_on = None

UTILITIES = ("power", "water", "sewer", "stormwater", "telecom")


def upgrade() -> None:
    for utility in UTILITIES:
        for suffix, length in (
            ("network_availability", 32),
            ("connection_status", 32),
            ("requirements", 500),
        ):
            op.add_column("land_parcels", sa.Column(f"{utility}_{suffix}", sa.String(length)))
        op.execute(
            sa.text(
                f"UPDATE land_parcels SET {utility}_network_availability = "
                f"CASE WHEN {utility}_available THEN 'available' "
                f"WHEN {utility}_available = false THEN 'unavailable' ELSE NULL END"
            )
        )


def downgrade() -> None:
    for utility in UTILITIES:
        if op.get_bind().scalar(
            sa.text(
                f"SELECT EXISTS (SELECT 1 FROM land_parcels WHERE "
                f"{utility}_connection_status IS NOT NULL OR {utility}_requirements IS NOT NULL "
                f"OR {utility}_network_availability IN ('conditional', 'not_checked'))"
            )
        ):
            raise RuntimeError("Utility details exist; retain this migration and roll forward.")
    for utility in UTILITIES:
        for suffix in ("network_availability", "connection_status", "requirements"):
            op.drop_column("land_parcels", f"{utility}_{suffix}")
