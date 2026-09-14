"""Technical specification register; no project claims are pre-populated."""

import sqlalchemy as sa
from alembic import op

revision = "0031_technical_specs"
down_revision = "0030_unit_removal"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "technical_specifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("scope", sa.String(16), nullable=False),
        sa.Column("applies_to", sa.String(300), nullable=False),
        sa.Column("description", sa.String(4000), nullable=False),
        sa.Column("brand_model", sa.String(300), nullable=False),
        sa.Column("inclusion", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("source_reference", sa.String(500), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "category IN ('structure','finishes','sanitary','plumbing','water',"
            "'aluminium','doors','kitchen','electrical','heating_cooling','shared','other')",
            name="category_allowed",
        ),
        sa.CheckConstraint("scope IN ('project','units')", name="scope_allowed"),
        sa.CheckConstraint(
            "inclusion IN ('included','optional','excluded','undecided')", name="inclusion_allowed"
        ),
        sa.CheckConstraint("status IN ('draft','confirmed')", name="status_allowed"),
        sa.CheckConstraint(
            "length(trim(title)) > 0 AND length(trim(applies_to)) > 0 "
            "AND length(trim(description)) > 0",
            name="text_required",
        ),
        sa.CheckConstraint(
            "status != 'confirmed' OR (length(trim(source_reference)) > 0 "
            "AND inclusion != 'undecided')",
            name="confirmation_source",
        ),
        sa.CheckConstraint("version > 0", name="version_positive"),
    )
    op.create_index(
        "ix_technical_specifications_project_id", "technical_specifications", ["project_id"]
    )


def downgrade() -> None:
    if op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT 1 FROM technical_specifications)")):
        raise RuntimeError(
            "Technical specifications or retained confirmations exist. Export before rollback; "
            "use a forward fix for retained evidence."
        )
    op.drop_table("technical_specifications")
