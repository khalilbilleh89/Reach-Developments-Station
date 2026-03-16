"""create unit qualitative attributes table

Revision ID: 0018
Revises: 0017
Create Date: 2026-03-16

Adds the unit_qualitative_attributes table — structured qualitative pricing
attributes per unit:
  - view_type: categorical view classification (city, sea, park, interior)
  - corner_unit: boolean flag for corner units
  - floor_premium_category: floor value tier (standard, premium, penthouse)
  - orientation: cardinal orientation (N, S, E, W, NE, NW, SE, SW)
  - outdoor_area_premium: outdoor space treatment (none, balcony, terrace, roof_garden)
  - upgrade_flag: boolean flag for finish/interior upgrades
  - notes: optional free-text analyst commentary

One record per unit enforced via unique constraint on unit_id.
These attributes provide qualitative context for pricing decisions and prepare
the system for future pricing automation.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "unit_qualitative_attributes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "unit_id",
            sa.String(36),
            sa.ForeignKey("units.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("view_type", sa.String(50), nullable=True),
        sa.Column("corner_unit", sa.Boolean, nullable=True),
        sa.Column("floor_premium_category", sa.String(50), nullable=True),
        sa.Column("orientation", sa.String(10), nullable=True),
        sa.Column("outdoor_area_premium", sa.String(50), nullable=True),
        sa.Column("upgrade_flag", sa.Boolean, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_unit_qualitative_attributes_unit_id",
        "unit_qualitative_attributes",
        ["unit_id"],
    )
    op.create_check_constraint(
        "ck_unit_qualitative_view_type",
        "unit_qualitative_attributes",
        "view_type IN ('city', 'sea', 'park', 'interior') OR view_type IS NULL",
    )
    op.create_check_constraint(
        "ck_unit_qualitative_floor_premium_category",
        "unit_qualitative_attributes",
        "floor_premium_category IN ('standard', 'premium', 'penthouse') OR floor_premium_category IS NULL",
    )
    op.create_check_constraint(
        "ck_unit_qualitative_orientation",
        "unit_qualitative_attributes",
        "orientation IN ('N', 'S', 'E', 'W', 'NE', 'NW', 'SE', 'SW') OR orientation IS NULL",
    )
    op.create_check_constraint(
        "ck_unit_qualitative_outdoor_area_premium",
        "unit_qualitative_attributes",
        "outdoor_area_premium IN ('none', 'balcony', 'terrace', 'roof_garden') OR outdoor_area_premium IS NULL",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_unit_qualitative_attributes_unit_id",
        table_name="unit_qualitative_attributes",
    )
    op.drop_table("unit_qualitative_attributes")
