"""Sales explanation alongside the authoritative technical specification."""

import sqlalchemy as sa
from alembic import op

revision = "0051_specification_benefit"
down_revision = "0050_project_matrices"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "technical_specifications",
        sa.Column("buyer_benefit", sa.String(2000), nullable=False, server_default=""),
    )


def downgrade() -> None:
    if op.get_bind().scalar(
        sa.text("SELECT EXISTS (SELECT 1 FROM technical_specifications WHERE buyer_benefit != '')")
    ):
        raise RuntimeError("Buyer benefits exist. Export before rollback; use a forward fix.")
    op.drop_column("technical_specifications", "buyer_benefit")
