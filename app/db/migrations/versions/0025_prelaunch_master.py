"""Allow attributed Master self-confirmation of Pre-Launch expenses.

Downgrade refuses retained self-confirmations, including reversed history.
"""

import sqlalchemy as sa
from alembic import op

revision = "0025_prelaunch_master"
down_revision = "0024_merge_permits_inventory"
branch_labels = None
depends_on = None

TABLE = "cashflow_development_movements"
SEPARATION = "ck_cashflow_development_movements_confirmer_is_not_recorder"
VALID = "ck_cashflow_development_movements_master_confirmation_valid"


def upgrade() -> None:
    op.add_column(
        TABLE,
        sa.Column(
            "master_self_confirmed", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
    )
    op.drop_constraint(op.f(SEPARATION), TABLE, type_="check")
    op.create_check_constraint(
        op.f(SEPARATION),
        TABLE,
        "confirmed_by_user_id IS NULL OR confirmed_by_user_id <> recorded_by_user_id"
        " OR master_self_confirmed",
    )
    op.create_check_constraint(
        op.f(VALID),
        TABLE,
        "NOT master_self_confirmed OR (confirmed_by_user_id IS NOT NULL"
        " AND confirmed_by_user_id = recorded_by_user_id AND confirmed_at IS NOT NULL"
        " AND status IN ('confirmed', 'reversed')"
        " AND category IN ('land_fees', 'design', 'consultants', 'permits', 'utilities',"
        " 'insurance', 'developer_overhead', 'marketing', 'tax', 'other'))",
    )
    op.execute("""
        CREATE FUNCTION guard_prelaunch_master_confirmation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'UPDATE' AND OLD.confirmed_at IS NOT NULL THEN
                IF NEW.master_self_confirmed IS DISTINCT FROM OLD.master_self_confirmed
                   OR (OLD.master_self_confirmed AND (
                       NEW.confirmed_by_user_id IS DISTINCT FROM OLD.confirmed_by_user_id
                       OR NEW.recorded_by_user_id IS DISTINCT FROM OLD.recorded_by_user_id
                       OR NEW.confirmed_at IS DISTINCT FROM OLD.confirmed_at)) THEN
                    RAISE EXCEPTION 'Confirmation authority history cannot be changed';
                END IF;
                RETURN NEW;
            END IF;
            IF NEW.master_self_confirmed AND NOT EXISTS (
                SELECT 1 FROM users u JOIN user_roles ur ON ur.user_id = u.id
                JOIN roles r ON r.id = ur.role_id
                WHERE u.id = NEW.confirmed_by_user_id AND u.is_active
                AND r.key = 'master_admin'
            ) THEN
                RAISE EXCEPTION 'Self-confirmation requires an active Master Administrator';
            END IF;
            RETURN NEW;
        END $$;
        CREATE TRIGGER prelaunch_master_confirmation
        BEFORE INSERT OR UPDATE ON cashflow_development_movements
        FOR EACH ROW EXECUTE FUNCTION guard_prelaunch_master_confirmation();
    """)


def downgrade() -> None:
    if op.get_bind().scalar(
        sa.text(f"SELECT EXISTS (SELECT 1 FROM {TABLE} WHERE master_self_confirmed)")
    ):
        raise RuntimeError(
            "Retained Master self-confirmations prevent downgrade; "
            "preserve history and roll forward."
        )
    op.execute(f"DROP TRIGGER prelaunch_master_confirmation ON {TABLE}")
    op.execute("DROP FUNCTION guard_prelaunch_master_confirmation()")
    op.drop_constraint(op.f(VALID), TABLE, type_="check")
    op.drop_constraint(op.f(SEPARATION), TABLE, type_="check")
    op.create_check_constraint(
        op.f(SEPARATION),
        TABLE,
        "confirmed_by_user_id IS NULL OR confirmed_by_user_id <> recorded_by_user_id",
    )
    op.drop_column(TABLE, "master_self_confirmed")
