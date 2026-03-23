"""add contractor and procurement tables

Revision ID: 0049
Revises: 0048
Create Date: 2026-03-23

PR-CONSTR-043 — Contractor & Procurement Tracking

Changes
-------
construction_contractors
  New table. Stores contractor registry within the construction module.

construction_procurement_packages
  New table. Stores procurement packages linked to construction scopes and
  optionally to a contractor.

construction_package_milestones
  Join table linking procurement packages to construction milestones
  (many-to-many).

No destructive changes. Existing tables are unmodified.

Migration Required: Yes
Backfill Required: No
Destructive Change: No
Rollback Safe: Yes
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0049"
down_revision: Union[str, None] = "0048"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "construction_contractors",
        sa.Column("id", sa.String(36), nullable=False, primary_key=True),
        sa.Column("contractor_code", sa.String(50), nullable=False),
        sa.Column("contractor_name", sa.String(255), nullable=False),
        sa.Column("contractor_type", sa.String(50), nullable=False),
        sa.Column("contact_name", sa.String(255), nullable=True),
        sa.Column("contact_email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
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
        sa.UniqueConstraint("contractor_code", name="uq_construction_contractor_code"),
    )

    op.create_table(
        "construction_procurement_packages",
        sa.Column("id", sa.String(36), nullable=False, primary_key=True),
        sa.Column(
            "scope_id",
            sa.String(36),
            sa.ForeignKey("construction_scopes.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "contractor_id",
            sa.String(36),
            sa.ForeignKey("construction_contractors.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("package_code", sa.String(50), nullable=False),
        sa.Column("package_name", sa.String(255), nullable=False),
        sa.Column("package_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("planned_value", sa.Numeric(18, 2), nullable=True),
        sa.Column("awarded_value", sa.Numeric(18, 2), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
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
        sa.UniqueConstraint(
            "scope_id",
            "package_code",
            name="uq_procurement_package_scope_code",
        ),
    )

    op.create_table(
        "construction_package_milestones",
        sa.Column(
            "package_id",
            sa.String(36),
            sa.ForeignKey(
                "construction_procurement_packages.id", ondelete="CASCADE"
            ),
            primary_key=True,
        ),
        sa.Column(
            "milestone_id",
            sa.String(36),
            sa.ForeignKey("construction_milestones.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )


def downgrade() -> None:
    op.drop_table("construction_package_milestones")
    op.drop_table("construction_procurement_packages")
    op.drop_table("construction_contractors")
