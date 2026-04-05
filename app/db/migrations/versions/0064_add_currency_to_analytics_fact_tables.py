"""add currency to analytics fact tables

Revision ID: 0064
Revises: 0063
Create Date: 2026-04-05

PR-CURRENCY-006 — Analytics Fact Table Currency Integrity

Changes
-------
fact_revenue
  currency  VARCHAR(10)  NOT NULL  DEFAULT 'AED'
    Added.  Populated from project.base_currency at ETL time.
    Backfilled from projects.base_currency via a correlated UPDATE.

fact_collections
  currency  VARCHAR(10)  NOT NULL  DEFAULT 'AED'
    Added.  Populated from project.base_currency at ETL time.
    Backfilled from projects.base_currency via a correlated UPDATE.

fact_receivables_snapshot
  currency  VARCHAR(10)  NOT NULL  DEFAULT 'AED'
    Added.  Populated from project.base_currency at ETL time.
    Backfilled from projects.base_currency via a correlated UPDATE.

Why the server_default is a literal 'AED' and not the Python constant
----------------------------------------------------------------------
Alembic migrations are immutable historical artefacts.  Using the Python
DEFAULT_CURRENCY constant here would create a runtime coupling between the
migration and future constant changes.  The literal 'AED' is the platform
default *at migration time* and is the correct backfill for pre-existing rows
that had no currency column.  Runtime code (ORM models, ETL services) imports
DEFAULT_CURRENCY so future changes propagate automatically to new inserts.

Migration Required: Yes
Backfill Required:  Yes (correlated UPDATE from projects.base_currency)
Destructive Change: No
Rollback Safe:      Yes
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect as sa_inspect

# ---------------------------------------------------------------------------
# Alembic revision identifiers
# ---------------------------------------------------------------------------

revision: str = "0064"
down_revision: Union[str, None] = "0063"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DEFAULT = "AED"  # platform canonical default at migration time


def _column_exists(table: str, column: str) -> bool:
    """Return True if *column* already exists on *table* in the connected DB.

    Used to make each DDL step idempotent so that upgrade is safe on:
      - a fresh database (column absent → added),
      - a partially-migrated or drifted database (column present → skipped),
      - a retry after a previously-interrupted migration run.
    """
    bind = op.get_bind()
    insp = sa_inspect(bind)
    return column in {c["name"] for c in insp.get_columns(table)}


def _add_and_backfill_currency(table: str) -> None:
    """Add a non-null currency VARCHAR(10) column with 'AED' server default
    and backfill from projects.base_currency.

    Idempotent: no-op when the column already exists.
    """
    if _column_exists(table, "currency"):
        return

    op.add_column(
        table,
        sa.Column(
            "currency",
            sa.String(10),
            nullable=False,
            server_default=sa.text(f"'{_DEFAULT}'"),
        ),
    )

    # Backfill existing rows from the project source-of-truth.
    # The correlated UPDATE sets currency to the project's base_currency for
    # every row that was inserted before this migration ran.  Rows added after
    # this migration will get the server_default ('AED') and then be
    # immediately overwritten by the ETL service which reads project.base_currency.
    bind = op.get_bind()
    bind.execute(
        sa.text(
            f"""
            UPDATE {table}
            SET currency = projects.base_currency
            FROM projects
            WHERE {table}.project_id = projects.id
            """
        )
    )


def _drop_currency_column(table: str) -> None:
    if _column_exists(table, "currency"):
        op.drop_column(table, "currency")


# ---------------------------------------------------------------------------
# Upgrade
# ---------------------------------------------------------------------------


def upgrade() -> None:
    _add_and_backfill_currency("fact_revenue")
    _add_and_backfill_currency("fact_collections")
    _add_and_backfill_currency("fact_receivables_snapshot")


# ---------------------------------------------------------------------------
# Downgrade
# ---------------------------------------------------------------------------


def downgrade() -> None:
    _drop_currency_column("fact_receivables_snapshot")
    _drop_currency_column("fact_collections")
    _drop_currency_column("fact_revenue")
