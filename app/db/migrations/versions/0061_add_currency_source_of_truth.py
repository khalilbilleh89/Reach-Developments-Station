"""Add currency source-of-truth: project base_currency + missing monetary columns

Revision ID: 0061
Revises: 0060
Create Date: 2026-04-04

PR-CURRENCY-002 — Currency Source-of-Truth, Schema Coverage & Project Base
                  Currency Foundation
PR-V7-09B — Made idempotent so upgrade is safe on fresh DB, partially-migrated
             DB, and drifted DB where columns already exist.

Summary
-------
This migration establishes the currency data foundation required for safe
financial enforcement in later PRs.  It does NOT change any formulas or
aggregation behaviour — it only adds denomination fields so that every stored
monetary value carries an explicit currency code.

Each DDL operation is wrapped with an existence check so the migration is
idempotent: re-running it on a database that already has the columns (e.g.
schema drift or a previously-interrupted run) is a no-op.

Changes
-------

projects
  base_currency  VARCHAR(10)  NOT NULL DEFAULT 'AED'
    The governing currency for all financial records linked to this project.
    Backfill: all existing rows set to 'AED' (canonical platform default).

sales_contracts
  currency  VARCHAR(10)  NOT NULL DEFAULT 'AED'
    Denomination of contract_price.
    Backfill: all existing rows set to 'AED'.

payment_schedules
  currency  VARCHAR(10)  NOT NULL DEFAULT 'AED'
    Denomination of due_amount.
    Backfill: all existing rows set to 'AED'.

payment_receipts
  currency  VARCHAR(10)  NOT NULL DEFAULT 'AED'
    Denomination of amount_received.
    Backfill: all existing rows set to 'AED'.

commission_payouts
  currency  VARCHAR(10)  NOT NULL DEFAULT 'AED'
    Denomination of gross_sale_value and commission_pool_value.
    Backfill: all existing rows set to 'AED'.

commission_payout_lines
  currency  VARCHAR(10)  NOT NULL DEFAULT 'AED'
    Denomination of amount.
    Backfill: all existing rows set to 'AED'.

feasibility_assumptions
  currency  VARCHAR(10)  NOT NULL DEFAULT 'AED'
    Denomination of avg_sale_price_per_sqm and construction_cost_per_sqm.
    Backfill: all existing rows set to 'AED'.

feasibility_results
  currency  VARCHAR(10)  NOT NULL DEFAULT 'AED'
    Denomination of gdv, total_cost, developer_profit, etc.
    Backfill: all existing rows set to 'AED'.

financial_scenario_runs
  currency  VARCHAR(10)  NOT NULL DEFAULT 'AED'
    Denomination of npv and gross_profit scalar outputs.
    Backfill: all existing rows set to 'AED'.

land_parcels
  currency  VARCHAR(10)  NOT NULL DEFAULT 'AED'  (was nullable without default)
    Denomination of acquisition_price and transaction_cost.
    Backfill: NULL rows set to 'AED'.

land_valuations
  currency  VARCHAR(10)  NOT NULL DEFAULT 'AED'
    Denomination of expected_gdv, expected_cost, residual_land_value, etc.
    Backfill: all existing rows set to 'AED'.

sales_exceptions
  currency  VARCHAR(10)  NOT NULL DEFAULT 'AED'
    Denomination of base_price, requested_price, and discount_amount.
    Backfill: all existing rows set to 'AED'.

construction_cost_comparison_sets
  currency  VARCHAR(10)  NOT NULL DEFAULT 'AED'
    Denomination of all line amounts within this comparison set.
    Backfill: all existing rows set to 'AED'.

cashflow_forecast_periods
  currency  VARCHAR(10)  NOT NULL DEFAULT 'AED'
    Denomination of inflows, outflows, and balance columns.
    Backfill: all existing rows set to 'AED'.

contract_payment_schedule
  (column already exists — no change to structure, only default normalised
   in ORM layer; no DDL needed)

Normalisation of existing currency columns
  land_parcels.currency — changed from nullable (no default) to NOT NULL DEFAULT 'AED'.
    This is achieved by: filling NULL → 'AED', then altering to NOT NULL.
    Safe because NULL meant "unknown", which we now make explicit as AED.

Backfill Strategy
-----------------
All existing rows receive the platform canonical default 'AED'.
This is the correct controlled fallback per the PR spec:
  "Use canonical DEFAULT_CURRENCY as controlled fallback for backfill where
   parent currency cannot be safely inferred from existing data."
The choice is deliberately conservative and documented here so that platform
administrators can perform targeted project-level corrections if any historical
project used a different currency before this migration landed.

Migration Required:  Yes
Backfill Required:   Yes
Destructive Change:  No
Rollback Safe:       Yes (column additions + backfill are reversible via downgrade)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect as sa_inspect

# ---------------------------------------------------------------------------
# Alembic revision identifiers
# ---------------------------------------------------------------------------

revision: str = "0061"
down_revision: Union[str, None] = "0060"
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


def _add_currency_column(table: str) -> None:
    """Add a non-null currency VARCHAR(10) column with 'AED' server default.

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


def _drop_currency_column(table: str) -> None:
    if _column_exists(table, "currency"):
        op.drop_column(table, "currency")


# ---------------------------------------------------------------------------
# Upgrade
# ---------------------------------------------------------------------------


def upgrade() -> None:
    # -- projects: add base_currency ----------------------------------------
    # Idempotent: skip if the column already exists (e.g. schema drift or a
    # previously-interrupted migration run).
    if not _column_exists("projects", "base_currency"):
        op.add_column(
            "projects",
            sa.Column(
                "base_currency",
                sa.String(10),
                nullable=False,
                server_default=sa.text(f"'{_DEFAULT}'"),
            ),
        )

    # -- sales_contracts: add currency -------------------------------------
    _add_currency_column("sales_contracts")

    # -- payment_schedules: add currency -----------------------------------
    _add_currency_column("payment_schedules")

    # -- payment_receipts: add currency ------------------------------------
    _add_currency_column("payment_receipts")

    # -- commission_payouts: add currency ----------------------------------
    _add_currency_column("commission_payouts")

    # -- commission_payout_lines: add currency -----------------------------
    _add_currency_column("commission_payout_lines")

    # -- feasibility_assumptions: add currency -----------------------------
    _add_currency_column("feasibility_assumptions")

    # -- feasibility_results: add currency ---------------------------------
    _add_currency_column("feasibility_results")

    # -- financial_scenario_runs: add currency -----------------------------
    _add_currency_column("financial_scenario_runs")

    # -- land_parcels: fill NULLs then make NOT NULL -----------------------
    # land_parcels.currency already exists but is nullable with no default.
    # Only perform the alter when the column is still nullable — if it was
    # already converted to NOT NULL (e.g. by a prior partial run) we skip.
    bind = op.get_bind()
    insp = sa_inspect(bind)
    lp_col_map = {c["name"]: c for c in insp.get_columns("land_parcels")}
    if "currency" in lp_col_map and lp_col_map["currency"]["nullable"]:
        # 1. Backfill any NULL values to 'AED'.
        op.execute(
            sa.text(
                f"UPDATE land_parcels SET currency = '{_DEFAULT}' WHERE currency IS NULL"
            )
        )
        # 2. Alter to NOT NULL with server default.
        op.alter_column(
            "land_parcels",
            "currency",
            existing_type=sa.String(10),
            nullable=False,
            server_default=sa.text(f"'{_DEFAULT}'"),
        )

    # -- land_valuations: add currency -------------------------------------
    _add_currency_column("land_valuations")

    # -- sales_exceptions: add currency ------------------------------------
    _add_currency_column("sales_exceptions")

    # -- construction_cost_comparison_sets: add currency -------------------
    _add_currency_column("construction_cost_comparison_sets")

    # -- cashflow_forecast_periods: add currency ---------------------------
    _add_currency_column("cashflow_forecast_periods")


# ---------------------------------------------------------------------------
# Downgrade
# ---------------------------------------------------------------------------


def downgrade() -> None:
    # Reverse all additions in reverse order — each drop is guarded so the
    # downgrade is also idempotent.
    _drop_currency_column("cashflow_forecast_periods")
    _drop_currency_column("construction_cost_comparison_sets")
    _drop_currency_column("sales_exceptions")
    _drop_currency_column("land_valuations")

    # land_parcels: revert to nullable (no server default)
    bind = op.get_bind()
    insp = sa_inspect(bind)
    lp_col_map = {c["name"]: c for c in insp.get_columns("land_parcels")}
    if "currency" in lp_col_map and not lp_col_map["currency"]["nullable"]:
        op.alter_column(
            "land_parcels",
            "currency",
            existing_type=sa.String(10),
            nullable=True,
            server_default=None,
        )

    _drop_currency_column("financial_scenario_runs")
    _drop_currency_column("feasibility_results")
    _drop_currency_column("feasibility_assumptions")
    _drop_currency_column("commission_payout_lines")
    _drop_currency_column("commission_payouts")
    _drop_currency_column("payment_receipts")
    _drop_currency_column("payment_schedules")
    _drop_currency_column("sales_contracts")

    if _column_exists("projects", "base_currency"):
        op.drop_column("projects", "base_currency")
