"""add code and description fields to phases

Revision ID: 0014
Revises: 0013
Create Date: 2026-03-15

Adds additional metadata fields to the phases table:
  - code: short identifier for the phase (optional)
  - description: free-text description of the phase (optional)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("phases", sa.Column("code", sa.String(100), nullable=True))
    op.add_column("phases", sa.Column("description", sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_column("phases", "description")
    op.drop_column("phases", "code")
