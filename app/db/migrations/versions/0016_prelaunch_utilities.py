"""Allow utilities as a governed Development Movement category."""

from alembic import op

revision = "0016_prelaunch_utilities"
down_revision = "0015_construction_stages"
branch_labels = None
depends_on = None

_CONSTRAINT = "ck_cashflow_development_movements_category_ok"
_OLD = (
    "category IN ('land_acquisition', 'land_fees', 'design', 'consultants', 'permits', "
    "'insurance', 'developer_overhead', 'marketing', 'commissions', 'tax', 'handover', "
    "'other')"
)
_NEW = (
    "category IN ('land_acquisition', 'land_fees', 'design', 'consultants', 'permits', "
    "'utilities', 'insurance', 'developer_overhead', 'marketing', 'commissions', 'tax', "
    "'handover', 'other')"
)


def upgrade() -> None:
    op.drop_constraint(_CONSTRAINT, "cashflow_development_movements", type_="check")
    op.create_check_constraint(_CONSTRAINT, "cashflow_development_movements", _NEW)


def downgrade() -> None:
    # Refuse a lossy downgrade instead of deleting or relabelling valid rows.
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM cashflow_development_movements "
        "WHERE category = 'utilities') THEN RAISE EXCEPTION "
        "'cannot downgrade while utilities movements exist'; END IF; END $$"
    )
    op.drop_constraint(_CONSTRAINT, "cashflow_development_movements", type_="check")
    op.create_check_constraint(_CONSTRAINT, "cashflow_development_movements", _OLD)
