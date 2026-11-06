"""Reconcile legacy preparation statuses with recorded actual permit dates."""

import sqlalchemy as sa
from alembic import op

revision = "0063_permit_date_reconcile"
down_revision = "0062_project_training"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Only repair pre-submission records. Do not override a deliberate rejection,
    # hold, withdrawal, expiry or later authority decision. No invented human
    # actor: this is a system migration audit, not a new authority decision.
    op.execute(
        sa.text("""
        WITH candidates AS (
            SELECT p.id, to_jsonb(p) AS old_data,
                   milestone.status, milestone.day
            FROM permits p
            CROSS JOIN LATERAL (
                SELECT status, day FROM (VALUES
                    ('submitted', p.actual_submission_date, 1),
                    ('accepted_for_review', p.accepted_for_review_date, 2),
                    ('comments_received', p.comments_received_date, 3),
                    ('resubmission', p.resubmission_date, 4),
                    ('completed', p.issue_date, 5),
                    ('renewed', p.renewal_date, 6)
                ) AS dates(status, day, priority)
                WHERE day IS NOT NULL
                ORDER BY day DESC, priority DESC LIMIT 1
            ) milestone
            WHERE p.deleted_at IS NULL AND p.status IN ('not_started', 'preparing')
        ), corrected AS (
            UPDATE permits p SET status = c.status,
                status_effective_date = c.day, updated_at = now()
            FROM candidates c WHERE p.id = c.id
            RETURNING p.id, c.old_data, to_jsonb(p) AS new_data
        )
        INSERT INTO audit_events (
            id, action, entity_type, entity_id, actor_user_id, source,
            correlation_id, reason, before_data, after_data
        )
        SELECT gen_random_uuid(), 'permit.dates_reconciled', 'permit', id, NULL,
            'migration', gen_random_uuid(),
            '0063: reconcile existing actual dates; no new authority decision',
            old_data, new_data
        FROM corrected
    """)
    )


def downgrade() -> None:
    # No schema changed. Keep corrected facts and append-only audit evidence;
    # restoring the knowingly stale state would reintroduce the defect.
    pass
