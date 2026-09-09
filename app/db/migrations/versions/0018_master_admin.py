"""Add the explicit Master Administrator authority override.

The role is intentionally separate from System Administrator. It is the one
auditable identity that may exercise every fixed authority and bypass
maker/checker separation when the business owner needs an emergency override.
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op

revision = "0018_master_admin"
down_revision = "0017_consultant_commissions"
branch_labels = None
depends_on = None

_ROLE_NAMESPACE = uuid.UUID("6f6d4a1e-6f2b-5c9f-9a3e-1c2d3e4f5a6b")
_MASTER_ROLE_ID = uuid.uuid5(_ROLE_NAMESPACE, "master_admin")


def upgrade() -> None:
    roles = sa.table(
        "roles",
        sa.column("id", sa.UUID()),
        sa.column("key", sa.String()),
        sa.column("label", sa.String()),
    )
    op.bulk_insert(
        roles,
        [{"id": _MASTER_ROLE_ID, "key": "master_admin", "label": "Master Administrator"}],
    )


def downgrade() -> None:
    user_roles = sa.table(
        "user_roles",
        sa.column("user_id", sa.UUID()),
        sa.column("role_id", sa.UUID()),
    )
    roles = sa.table(
        "roles",
        sa.column("id", sa.UUID()),
        sa.column("key", sa.String()),
    )
    op.execute(user_roles.delete().where(user_roles.c.role_id == _MASTER_ROLE_ID))
    op.execute(roles.delete().where(roles.c.id == _MASTER_ROLE_ID))
