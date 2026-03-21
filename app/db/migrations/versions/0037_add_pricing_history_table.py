"""add pricing history table

Revision ID: 0037
Revises: 0036
Create Date: 2026-03-21

PR-15 — Pricing History & Audit Trail Hardening

Creates the ``pricing_history`` table — an append-only audit log that records
a snapshot of the pricing record state at the moment of each governed change
event.

Columns:

  id                   — UUID primary key.
  pricing_id           — FK to unit_pricing.id (CASCADE).
  unit_id              — FK to units.id (CASCADE), denormalised for fast lookups.
  change_type          — Why the snapshot was taken:
                         INITIAL | MANUAL_UPDATE | PREMIUM_RECALC |
                         OVERRIDE | APPROVAL | ARCHIVE
  base_price           — Snapshot of the base price at the time of change.
  manual_adjustment    — Snapshot of the manual adjustment at the time of change.
  final_price          — Snapshot of the computed final price at the time of change.
  pricing_status       — Snapshot of the pricing lifecycle status at change time.
  currency             — Currency code (snapshot).
  override_reason      — Justification note, populated on OVERRIDE events.
  override_requested_by — Requester identifier, populated on OVERRIDE events.
  override_approved_by  — Approver identifier, populated on OVERRIDE events.
  actor                — Identifier of the user/system that triggered the change.
  created_at           — UTC timestamp when the audit entry was created.
  updated_at           — Mirrors created_at; never updated after insert.

Indexes:
  ix_pricing_history_pricing_id  — supports audit trail lookups by record.
  ix_pricing_history_unit_id     — supports unit-scoped history queries.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0037"
down_revision: Union[str, None] = "0036"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pricing_history",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column(
            "pricing_id",
            sa.String(36),
            sa.ForeignKey("unit_pricing.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "unit_id",
            sa.String(36),
            sa.ForeignKey("units.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("change_type", sa.String(30), nullable=False),
        sa.Column("base_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("manual_adjustment", sa.Numeric(14, 2), nullable=False),
        sa.Column("final_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("pricing_status", sa.String(20), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, server_default="AED"),
        sa.Column("override_reason", sa.Text, nullable=True),
        sa.Column("override_requested_by", sa.String(255), nullable=True),
        sa.Column("override_approved_by", sa.String(255), nullable=True),
        sa.Column("actor", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("pricing_history")
