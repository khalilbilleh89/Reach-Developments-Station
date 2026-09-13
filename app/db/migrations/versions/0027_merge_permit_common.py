"""Join permit completion and common-area histories without rewriting either."""

revision = "0027_merge_permit_common"
down_revision = ("0026_permit_completed", "0026_common_areas")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
