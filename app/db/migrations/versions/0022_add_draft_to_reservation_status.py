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

PostgreSQL is the supported migrated-environment target.
On PostgreSQL the old constraint is dropped and recreated.

SQLite note:
  This migration is intentionally a no-op on SQLite.  Modern SQLite versions
  do enforce CHECK constraints, but Alembic cannot modify a CHECK constraint
  on SQLite without a full batch table recreation, which adds complexity beyond
  the scope of this PR.  SQLite is used exclusively for local development and
  automated testing (via Base.metadata.create_all), where Alembic migrations
  are never run.  Any schema drift on SQLite for already-migrated environments
  is an accepted limitation; it does not affect production (PostgreSQL) or the
  test suite (in-memory SQLite with schema created from models, not migrations).
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
    # SQLite: intentionally a no-op.  Alembic cannot modify a CHECK constraint
    # on SQLite without a batch table recreation.  SQLite is only used for the
    # test suite (schema built from ORM models, not migrations), so this
    # migration is safe to skip there.  PostgreSQL is the only supported
    # target for already-migrated production environments.


def downgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "postgresql":
        op.drop_constraint(_OLD_CONSTRAINT, _TABLE, type_="check")
        op.create_check_constraint(_OLD_CONSTRAINT, _TABLE, _OLD_CHECK)
