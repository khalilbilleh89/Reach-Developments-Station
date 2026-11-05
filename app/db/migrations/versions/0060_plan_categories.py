"""Separate plan disciplines without reclassifying existing evidence."""

import sqlalchemy as sa
from alembic import op

revision = "0060_plan_categories"
down_revision = "0059_marketing_assets"
branch_labels = None
depends_on = None

OLD = "category IN ('general','architecture','structure','mep','landscape','interiors')"
NEW = (
    "category IN ('general','architecture','structure','mep','landscape','interiors',"
    "'electrical','mechanical','shop_drawing')"
)


def constraint(expression: str) -> None:
    op.drop_constraint(
        op.f("ck_project_drawings_valid_category"), "project_drawings", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_project_drawings_valid_category"), "project_drawings", expression
    )


def upgrade() -> None:
    constraint(NEW)


def downgrade() -> None:
    if op.get_bind().scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM project_drawings "
            "WHERE category IN ('electrical','mechanical','shop_drawing'))"
        )
    ):
        raise RuntimeError(
            "New plan categories exist, including retained history; downgrade refused."
        )
    constraint(OLD)
