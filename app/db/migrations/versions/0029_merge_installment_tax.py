"""Join installment VAT with the reviewed permit and Sales histories."""

revision = "0029_merge_installment_tax"
down_revision = ("0028_merge_permit_sales", "0026_installment_tax")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
