"""add unit apartment attributes

Revision ID: 0021
Revises: 0020
Create Date: 2026-03-17

Additive migration — adds apartment-specific unit master attributes to the
units table (Layer A: Unit Master Attributes).

New nullable columns (all non-breaking for existing rows):
  - bedrooms        Integer
  - bathrooms       Integer
  - floor_level     String(50)
  - livable_area    Numeric(10, 2)
  - has_roof_garden Boolean

roof_garden_area and balcony_area already existed from migration 0001.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0021"
down_revision: Union[str, None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("units", sa.Column("bedrooms", sa.Integer(), nullable=True))
    op.add_column("units", sa.Column("bathrooms", sa.Integer(), nullable=True))
    op.add_column("units", sa.Column("floor_level", sa.String(50), nullable=True))
    op.add_column("units", sa.Column("livable_area", sa.Numeric(10, 2), nullable=True))
    op.add_column("units", sa.Column("has_roof_garden", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("units", "has_roof_garden")
    op.drop_column("units", "livable_area")
    op.drop_column("units", "floor_level")
    op.drop_column("units", "bathrooms")
    op.drop_column("units", "bedrooms")
