"""add draft to unit_reservations status constraint

Revision ID: 0022
Revises: 0021
Create Date: 2026-03-17

Migration 0019 created the unit_reservations table with a CHECK constraint
that allowed only:
  'active', 'expired', 'cancelled', 'converted'

The reservation lifecycle state machine (PR-REDS-031) introduces a 'draft'
status so that reservations can be created in a provisional state before being
explicitly activated.  This migration widens the constraint to include 'draft'.

On PostgreSQL the old constraint is dropped and recreated.
SQLite does not enforce CHECK constraints at runtime, but the migration runs
cleanly on both engines so that existing test infrastructure is unaffected.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0022"
down_revision: Union[str, None] = "0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "unit_reservations"
_OLD_CONSTRAINT = "ck_unit_reservations_status"
_OLD_CHECK = "status IN ('active', 'expired', 'cancelled', 'converted')"
_NEW_CHECK = "status IN ('draft', 'active', 'expired', 'cancelled', 'converted')"


def upgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "postgresql":
        # PostgreSQL supports ALTER TABLE DROP CONSTRAINT / ADD CONSTRAINT.
        op.drop_constraint(_OLD_CONSTRAINT, _TABLE, type_="check")
        op.create_check_constraint(_OLD_CONSTRAINT, _TABLE, _NEW_CHECK)
    # SQLite: CHECK constraints cannot be modified via ALTER TABLE.
    # The constraint is not enforced at runtime by SQLite anyway, so no action
    # is needed for the test environment.


def downgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "postgresql":
        op.drop_constraint(_OLD_CONSTRAINT, _TABLE, type_="check")
        op.create_check_constraint(_OLD_CONSTRAINT, _TABLE, _OLD_CHECK)
