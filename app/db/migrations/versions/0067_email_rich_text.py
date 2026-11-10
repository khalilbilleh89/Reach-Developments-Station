"""Retain optional sanitized email formatting alongside the plain-text body."""

import sqlalchemy as sa
from alembic import op

revision = "0067_email_rich_text"
down_revision = "0066_client_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("commercial_emails", sa.Column("body_html", sa.Text(), nullable=True))
    op.create_check_constraint(
        "body_html_length", "commercial_emails", "body_html IS NULL OR length(body_html) <= 100000"
    )


def downgrade() -> None:
    if op.get_bind().scalar(
        sa.text("SELECT EXISTS (SELECT 1 FROM commercial_emails WHERE body_html IS NOT NULL)")
    ):
        raise RuntimeError(
            "Retained email formatting prevents downgrade. Export and resolve first."
        )
    op.drop_constraint("body_html_length", "commercial_emails", type_="check")
    op.drop_column("commercial_emails", "body_html")
