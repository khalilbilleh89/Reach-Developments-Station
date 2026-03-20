"""add performance indexes

Revision ID: 0031
Revises: 0030
Create Date: 2026-03-20

PR-E7 — System Performance Pass

Adds the missing indexes identified during the performance audit.

New indexes:
  registration_cases.status
      Speeds up the per-project case-count queries that filter on status
      (completed, open, cancelled).  The project_id index already exists;
      adding status allows the DB planner to satisfy
      ``WHERE project_id = ? AND status = ?`` or
      ``WHERE project_id = ? AND status NOT IN (?, ?)``
      without a full project-partition scan.

  registration_cases(project_id, status)  — composite
      A composite index on (project_id, status) covers the two most frequent
      aggregation patterns used by the registry summary endpoint:
        - count_completed_by_project:  WHERE project_id = ? AND status = ?
        - count_open_by_project:       WHERE project_id = ? AND status NOT IN (?, ?)
      The composite index is more selective than the two individual indexes
      and removes any residual need for a bitmap AND merge.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0031"
down_revision: Union[str, None] = "0030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # registration_cases — status filter index
    # ------------------------------------------------------------------
    op.create_index(
        "ix_registration_cases_status",
        "registration_cases",
        ["status"],
    )

    # ------------------------------------------------------------------
    # registration_cases — composite (project_id, status) index
    # Covers both count_completed_by_project and count_open_by_project
    # aggregation queries.
    # ------------------------------------------------------------------
    op.create_index(
        "ix_registration_cases_project_id_status",
        "registration_cases",
        ["project_id", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_registration_cases_project_id_status",
        table_name="registration_cases",
    )
    op.drop_index(
        "ix_registration_cases_status",
        table_name="registration_cases",
    )
