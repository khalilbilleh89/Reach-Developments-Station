"""Join permit completion and Sales histories without changing existing revisions."""

revision = "0028_merge_permit_sales"
down_revision = ("0027_merge_permit_common", "0027_merge_sales_areas")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
