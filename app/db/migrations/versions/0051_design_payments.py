"""Independent sub-consultants, stage fees and retained payment/PDF attribution."""

import sqlalchemy as sa
from alembic import op

revision = "0051_design_payments"
down_revision = "0050_project_matrices"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "consultant_engagements",
        sa.Column(
            "engagement_type", sa.String(16), nullable=False, server_default=sa.text("'main'")
        ),
    )
    op.create_check_constraint(
        op.f("ck_consultant_engagements_type_ok"),
        "consultant_engagements",
        "engagement_type IN ('main', 'subconsultant')",
    )
    op.drop_index("uq_ce_one_active_engagement", table_name="consultant_engagements")
    op.create_index(
        "uq_ce_one_active_engagement",
        "consultant_engagements",
        ["project_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active' AND engagement_type = 'main'"),
    )
    op.add_column("consultant_design_stages", sa.Column("agreed_payment_amount", sa.Numeric(18, 2)))
    op.create_check_constraint(
        op.f("ck_consultant_design_stages_payment_nonnegative"),
        "consultant_design_stages",
        "agreed_payment_amount IS NULL OR agreed_payment_amount >= 0",
    )
    op.create_table(
        "consultant_stage_payments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("request_id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("stage_id", sa.UUID(), nullable=False),
        sa.Column("movement_id", sa.UUID(), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.PrimaryKeyConstraint("id", name="pk_consultant_stage_payments"),
        sa.UniqueConstraint("id", "project_id", name="ce_payment_project"),
        sa.UniqueConstraint("project_id", "request_id", name="ce_payment_request"),
        sa.UniqueConstraint("movement_id", name="uq_consultant_stage_payments_movement_id"),
        sa.ForeignKeyConstraint(
            ["stage_id", "project_id"],
            ["consultant_design_stages.id", "consultant_design_stages.project_id"],
            name="ce_payment_stage",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["movement_id", "project_id"],
            ["cashflow_development_movements.id", "cashflow_development_movements.project_id"],
            name="ce_payment_movement",
            ondelete="RESTRICT",
        ),
    )
    op.create_table(
        "consultant_payment_proofs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("payment_id", sa.UUID(), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("document", sa.LargeBinary(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.PrimaryKeyConstraint("id", name="pk_consultant_payment_proofs"),
        sa.ForeignKeyConstraint(
            ["payment_id", "project_id"],
            ["consultant_stage_payments.id", "consultant_stage_payments.project_id"],
            name="ce_proof_payment",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_consultant_payment_proofs_created_by_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "octet_length(document) BETWEEN 1 AND 10485760",
            name=op.f("ck_consultant_payment_proofs_document_size"),
        ),
        sa.CheckConstraint(
            "length(trim(filename)) > 0", name=op.f("ck_consultant_payment_proofs_filename_present")
        ),
    )
    op.execute("""
        CREATE FUNCTION guard_design_payment_movement() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM consultant_stage_payments p
                JOIN consultant_design_stages s ON s.id = p.stage_id AND s.project_id = p.project_id
                WHERE p.movement_id = NEW.id AND (
                    NEW.project_id <> p.project_id OR NEW.category <> 'consultants'
                    OR NEW.movement_date < s.actual_completion_date
                    OR (NEW.status IN ('recorded', 'confirmed') AND s.status <> 'completed')
                )
            ) THEN
                RAISE EXCEPTION 'Stage payment must retain its consultant and completion basis'
                    USING ERRCODE = '23514', CONSTRAINT = 'design_payment_movement_guard';
            END IF;
            RETURN NEW;
        END $$;
        CREATE TRIGGER design_payment_movement_guard
        BEFORE UPDATE ON cashflow_development_movements
        FOR EACH ROW EXECUTE FUNCTION guard_design_payment_movement();
    """)


def downgrade() -> None:
    for query in (
        "SELECT EXISTS (SELECT 1 FROM consultant_stage_payments)",
        "SELECT EXISTS (SELECT 1 FROM consultant_payment_proofs)",
        "SELECT EXISTS (SELECT 1 FROM consultant_engagements "
        "WHERE engagement_type = 'subconsultant')",
        "SELECT EXISTS (SELECT 1 FROM consultant_design_stages "
        "WHERE agreed_payment_amount IS NOT NULL)",
    ):
        if op.get_bind().scalar(sa.text(query)):
            raise RuntimeError(
                "Retained Design payment or sub-consultant history prevents downgrade; "
                "roll forward."
            )
    op.execute("DROP TRIGGER design_payment_movement_guard ON cashflow_development_movements")
    op.execute("DROP FUNCTION guard_design_payment_movement()")
    op.drop_table("consultant_payment_proofs")
    op.drop_table("consultant_stage_payments")
    op.drop_constraint(
        op.f("ck_consultant_design_stages_payment_nonnegative"),
        "consultant_design_stages",
        type_="check",
    )
    op.drop_column("consultant_design_stages", "agreed_payment_amount")
    op.drop_index("uq_ce_one_active_engagement", table_name="consultant_engagements")
    op.create_index(
        "uq_ce_one_active_engagement",
        "consultant_engagements",
        ["project_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.drop_constraint(
        op.f("ck_consultant_engagements_type_ok"), "consultant_engagements", type_="check"
    )
    op.drop_column("consultant_engagements", "engagement_type")
