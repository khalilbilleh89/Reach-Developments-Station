"""add concept option promotion fields

Revision ID: 0051
Revises: 0050
Create Date: 2026-03-24

PR-CONCEPT-054 — Concept Option Promotion to Project Structuring

Changes
-------
concept_options
  is_promoted        BOOLEAN NOT NULL DEFAULT FALSE
  promoted_at        TIMESTAMP WITH TIME ZONE, nullable
  promoted_project_id VARCHAR(36), nullable
  promotion_notes    TEXT, nullable

These four columns persist the audit trail for a concept option that has
been promoted into a downstream project phase via the
POST /concept-options/{id}/promote endpoint.

No destructive changes. Existing rows default to is_promoted=FALSE with
all other promotion fields NULL.

Migration Required: Yes
Backfill Required: No
Destructive Change: No
Rollback Safe: Yes
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0051"
down_revision: Union[str, None] = "0050"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "concept_options",
        sa.Column(
            "is_promoted",
            sa.Boolean,
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "concept_options",
        sa.Column(
            "promoted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "concept_options",
        sa.Column(
            "promoted_project_id",
            sa.String(36),
            nullable=True,
        ),
    )
    op.add_column(
        "concept_options",
        sa.Column(
            "promotion_notes",
            sa.Text,
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("concept_options", "promotion_notes")
    op.drop_column("concept_options", "promoted_project_id")
    op.drop_column("concept_options", "promoted_at")
    op.drop_column("concept_options", "is_promoted")
