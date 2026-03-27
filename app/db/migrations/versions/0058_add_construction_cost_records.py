"""add construction cost records table

Revision ID: 0058
Revises: 0057
Create Date: 2026-03-27

PR-V6-09 — Construction Cost Record Foundation

Changes
-------
construction_cost_records
  New table providing a first-class, project-owned record for construction
  cost line items.  Each row captures one cost entry classified by category,
  source, and stage with a decimal amount, optional effective date, and a
  soft-delete flag (is_active).

  id               VARCHAR(36)     PK (UUID)
  project_id       VARCHAR(36)     FK → projects.id CASCADE DELETE
  title            VARCHAR(255)    NOT NULL
  cost_category    VARCHAR(50)     NOT NULL
  cost_source      VARCHAR(50)     NOT NULL
  cost_stage       VARCHAR(50)     NOT NULL
  amount           NUMERIC(20, 2)  NOT NULL
  currency         VARCHAR(10)     NOT NULL DEFAULT 'AED'
  effective_date   DATE            NULL
  reference_number VARCHAR(255)    NULL
  notes            TEXT            NULL
  is_active        BOOLEAN         NOT NULL DEFAULT TRUE
  created_at       TIMESTAMPTZ     NOT NULL
  updated_at       TIMESTAMPTZ     NOT NULL

Indexes
  ix_construction_cost_records_project_id
  ix_construction_cost_records_cost_category
  ix_construction_cost_records_cost_stage
  ix_construction_cost_records_is_active

Migration Required: Yes
Backfill Required: No
Destructive Change: No
Rollback Safe: Yes
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0058"
down_revision: Union[str, None] = "0057"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "construction_cost_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("cost_category", sa.String(50), nullable=False),
        sa.Column("cost_source", sa.String(50), nullable=False),
        sa.Column("cost_stage", sa.String(50), nullable=False),
        sa.Column("amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, server_default="AED"),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("reference_number", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
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

    op.create_index(
        "ix_construction_cost_records_project_id",
        "construction_cost_records",
        ["project_id"],
    )
    op.create_index(
        "ix_construction_cost_records_cost_category",
        "construction_cost_records",
        ["cost_category"],
    )
    op.create_index(
        "ix_construction_cost_records_cost_stage",
        "construction_cost_records",
        ["cost_stage"],
    )
    op.create_index(
        "ix_construction_cost_records_is_active",
        "construction_cost_records",
        ["is_active"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_construction_cost_records_is_active", table_name="construction_cost_records"
    )
    op.drop_index(
        "ix_construction_cost_records_cost_stage",
        table_name="construction_cost_records",
    )
    op.drop_index(
        "ix_construction_cost_records_cost_category",
        table_name="construction_cost_records",
    )
    op.drop_index(
        "ix_construction_cost_records_project_id",
        table_name="construction_cost_records",
    )
    op.drop_table("construction_cost_records")
