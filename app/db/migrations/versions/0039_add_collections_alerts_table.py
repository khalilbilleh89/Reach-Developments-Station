"""add collections alerts table

Revision ID: 0039
Revises: 0038
Create Date: 2026-03-21

PR-19 — Collections Alerts & Receipt Matching
PR-19A — Collections Alert Integrity & Schema Hardening

Creates the ``collections_alerts`` table — alert records generated when
installment obligations cross overdue-day thresholds (7 / 30 / 90 days).

Columns:

  id                   — UUID primary key.
  contract_id          — FK to sales_contracts.id (CASCADE).
  installment_id       — FK to contract_payment_schedule.id (CASCADE).
  alert_type           — Threshold tier: overdue_7_days | overdue_30_days | overdue_90_days.
  severity             — Severity: warning | critical | high_risk.
  days_overdue         — Days overdue at the time the alert was generated.
  outstanding_balance  — Outstanding balance at the time the alert was generated.
  resolved_at          — Timestamp when the alert was resolved (nullable).
  notes                — Optional notes (nullable).
  created_at           — UTC creation timestamp.
  updated_at           — UTC last-update timestamp.

Indexes:

  index on contract_id   — fast lookups by contract.
  index on severity      — supports severity-filtered queries.
  index on created_at    — supports time-ordered queries.

Uniqueness guard:

  uix_collections_alerts_active — PostgreSQL partial unique index on
  (contract_id, installment_id, alert_type) WHERE resolved_at IS NULL.
  Prevents duplicate unresolved alerts at the DB level under concurrent
  generation.  PostgreSQL-only; service-layer checks cover SQLite (tests).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0039"
down_revision: Union[str, None] = "0038"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "collections_alerts",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column(
            "contract_id",
            sa.String(36),
            sa.ForeignKey("sales_contracts.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "installment_id",
            sa.String(36),
            sa.ForeignKey("contract_payment_schedule.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "alert_type",
            sa.String(50),
            nullable=False,
            server_default=sa.text("'overdue_7_days'"),
        ),
        sa.Column(
            "severity",
            sa.String(50),
            nullable=False,
            server_default=sa.text("'warning'"),
            index=True,
        ),
        sa.Column("days_overdue", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column(
            "outstanding_balance",
            sa.Numeric(14, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.String(1000), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            index=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    # Partial unique index (PostgreSQL only): prevents duplicate unresolved alerts
    # for the same (contract, installment, alert_type) under concurrent generation.
    # SQLite (used in tests) does not support partial unique indexes with WHERE;
    # service-layer checks provide the equivalent guard in SQLite.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.create_index(
            "uix_collections_alerts_active",
            "collections_alerts",
            ["contract_id", "installment_id", "alert_type"],
            unique=True,
            postgresql_where=sa.text("resolved_at IS NULL"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.drop_index("uix_collections_alerts_active", table_name="collections_alerts")
    op.drop_table("collections_alerts")
