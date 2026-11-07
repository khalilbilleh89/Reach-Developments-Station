"""Optional Google Drive client folder and Odoo opportunity links."""

import sqlalchemy as sa
from alembic import op

revision = "0066_client_links"
down_revision = "0065_leasing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("clients", sa.Column("client_folder_url", sa.String(2000), nullable=True))
    op.add_column("clients", sa.Column("odoo_opportunity_url", sa.String(2000), nullable=True))


def downgrade() -> None:
    if op.get_bind().scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM clients WHERE client_folder_url IS NOT NULL "
            "OR odoo_opportunity_url IS NOT NULL)"
        )
    ):
        raise RuntimeError("Client links exist; clear them explicitly before downgrading.")
    op.drop_column("clients", "odoo_opportunity_url")
    op.drop_column("clients", "client_folder_url")
