"""add developer_name, start_date, target_end_date to projects

Revision ID: 0013
Revises: 0012
Create Date: 2026-03-15

Adds production-grade identity fields to the projects table:
  - developer_name: name of the developing company/entity
  - start_date: project commencement date
  - target_end_date: planned project completion date
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("developer_name", sa.String(255), nullable=True))
    op.add_column("projects", sa.Column("start_date", sa.Date, nullable=True))
    op.add_column("projects", sa.Column("target_end_date", sa.Date, nullable=True))


def downgrade() -> None:
    op.drop_column("projects", "target_end_date")
    op.drop_column("projects", "start_date")
    op.drop_column("projects", "developer_name")
