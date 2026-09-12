"""Add the completed permit status without rewriting history."""

import sqlalchemy as sa
from alembic import op

revision = "0025_permit_completed"
down_revision = "0024_merge_permits_inventory"
branch_labels = None
depends_on = None

_OLD = (
    "not_started",
    "preparing",
    "submitted",
    "accepted_for_review",
    "comments_received",
    "resubmission",
    "approved_with_conditions",
    "issued",
    "expired",
    "renewed",
    "rejected",
    "on_hold",
    "withdrawn",
)
_CHECKS = (
    ("permits", "status", "ck_permits_status_allowed"),
    ("permit_status_events", "from_status", "ck_permit_status_events_from_allowed"),
    ("permit_status_events", "to_status", "ck_permit_status_events_to_allowed"),
)


def _replace(statuses: tuple[str, ...]) -> None:
    allowed = ", ".join(f"'{value}'" for value in statuses)
    for table, column, name in _CHECKS:
        op.drop_constraint(op.f(name), table, type_="check")
        op.create_check_constraint(op.f(name), table, f"{column} IN ({allowed})")


def upgrade() -> None:
    _replace((*_OLD, "completed"))


def downgrade() -> None:
    for table, column, _ in _CHECKS:
        if op.get_bind().scalar(
            sa.text(f"SELECT EXISTS (SELECT 1 FROM {table} WHERE {column} = 'completed')")
        ):
            raise RuntimeError("Cannot downgrade while completed permit records/history exist.")
    _replace(_OLD)
