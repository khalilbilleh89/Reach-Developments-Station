"""Buyer sales-team information and per-transaction attribution snapshots.

Existing rows remain unknown rather than inventing historical attribution.
Downgrade removes only these optional fields; export them before rollback.
"""

import sqlalchemy as sa
from alembic import op

revision = "0025_sales_agent_details"
down_revision = "0024_merge_permits_inventory"
branch_labels = None
depends_on = None

FIELDS = ("agent_country", "agent_branch", "agent_branch_leader", "agent_name")
TABLES = ("clients", "reservations", "sale_contracts")


def upgrade() -> None:
    for table in TABLES:
        for field in FIELDS:
            op.add_column(table, sa.Column(field, sa.String(200), nullable=True))


def downgrade() -> None:
    for table in reversed(TABLES):
        for field in reversed(FIELDS):
            op.drop_column(table, field)
