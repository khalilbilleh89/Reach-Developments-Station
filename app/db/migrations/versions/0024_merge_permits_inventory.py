"""Merge independently developed permit removal and inventory configuration histories.

Revision ID: 0024_merge_permits_inventory
Revises: 0023_permit_removal, 0023_inventory_options
"""

revision = "0024_merge_permits_inventory"
down_revision = ("0023_permit_removal", "0023_inventory_options")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
