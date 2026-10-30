"""Optional reference images owned by technical specifications."""

import sqlalchemy as sa
from alembic import op

revision = "0054_specification_images"
down_revision = "0053_marketing_economics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name in ("scope_allowed", "text_required", "confirmation_source"):
        op.drop_constraint(
            op.f("ck_technical_specifications_" + name), "technical_specifications", type_="check"
        )
    op.create_check_constraint(
        op.f("ck_technical_specifications_scope_allowed"),
        "technical_specifications",
        "scope IN ('project','units','buildable')",
    )
    op.create_check_constraint(
        op.f("ck_technical_specifications_text_required"),
        "technical_specifications",
        "length(trim(title)) > 0 AND length(trim(description)) > 0",
    )
    op.create_check_constraint(
        op.f("ck_technical_specifications_confirmation_source"),
        "technical_specifications",
        "status != 'confirmed' OR inclusion != 'undecided'",
    )
    op.create_table(
        "specification_images",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("specification_id", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.String(200), nullable=False),
        sa.Column("image_data", sa.LargeBinary(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["specification_id"], ["technical_specifications.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        "ix_specification_images_specification_id", "specification_images", ["specification_id"]
    )


def downgrade() -> None:
    if op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT 1 FROM specification_images)")):
        raise RuntimeError("Specification images or retained evidence exist. Use a forward fix.")
    if op.get_bind().scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM technical_specifications WHERE scope = 'buildable' "
            "OR length(trim(applies_to)) = 0 OR "
            "(status = 'confirmed' AND length(trim(source_reference)) = 0))"
        )
    ):
        raise RuntimeError(
            "Optional specification fields or buildable-area scope cannot be represented "
            "before this revision. Use a forward fix."
        )
    op.drop_table("specification_images")
    for name in ("scope_allowed", "text_required", "confirmation_source"):
        op.drop_constraint(
            op.f("ck_technical_specifications_" + name), "technical_specifications", type_="check"
        )
    op.create_check_constraint(
        op.f("ck_technical_specifications_scope_allowed"),
        "technical_specifications",
        "scope IN ('project','units')",
    )
    op.create_check_constraint(
        op.f("ck_technical_specifications_text_required"),
        "technical_specifications",
        "length(trim(title)) > 0 AND length(trim(applies_to)) > 0 "
        "AND length(trim(description)) > 0",
    )
    op.create_check_constraint(
        op.f("ck_technical_specifications_confirmation_source"),
        "technical_specifications",
        "status != 'confirmed' OR (length(trim(source_reference)) > 0 "
        "AND inclusion != 'undecided')",
    )
