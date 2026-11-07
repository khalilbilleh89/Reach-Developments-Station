"""Retained owner leasing instructions and tenancy terms."""

import sqlalchemy as sa
from alembic import op

revision = "0065_leasing"
down_revision = "0064_permit_date_reconcile"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "leasing_instructions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("unit_id", sa.UUID(), nullable=False),
        sa.Column("owner_client_id", sa.UUID(), nullable=True),
        sa.Column("currency_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("mandate_date", sa.Date(), nullable=True),
        sa.Column("mandate_reference", sa.String(length=200), server_default="", nullable=False),
        sa.Column("asking_rent_monthly", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("available_from", sa.Date(), nullable=True),
        sa.Column("tenant_name", sa.String(length=200), server_default="", nullable=False),
        sa.Column("agreed_rent_monthly", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("security_deposit", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("lease_start", sa.Date(), nullable=True),
        sa.Column("lease_end", sa.Date(), nullable=True),
        sa.Column("agreement_reference", sa.String(length=200), server_default="", nullable=False),
        sa.Column("next_action", sa.String(length=300), server_default="", nullable=False),
        sa.Column("follow_up_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.String(length=4000), server_default="", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status != 'leased' OR (length(trim(tenant_name)) > 0 AND lease_start IS "
            "NOT NULL AND lease_end IS NOT NULL AND agreed_rent_monthly IS NOT NULL "
            "AND agreed_rent_monthly > 0 AND length(trim(agreement_reference)) > 0)",
            name=op.f("ck_leasing_instructions_tenancy"),
        ),
        sa.CheckConstraint(
            "status IN ('draft','marketing','negotiating','leased','closed')",
            name=op.f("ck_leasing_instructions_status"),
        ),
        sa.CheckConstraint(
            "status NOT IN ('marketing','negotiating','leased') OR (owner_client_id IS "
            "NOT NULL AND mandate_date IS NOT NULL AND length(trim(mandate_reference)) "
            "> 0 AND asking_rent_monthly IS NOT NULL AND asking_rent_monthly > 0)",
            name=op.f("ck_leasing_instructions_mandate"),
        ),
        sa.CheckConstraint(
            "agreed_rent_monthly IS NULL OR agreed_rent_monthly >= 0",
            name=op.f("ck_leasing_instructions_agreed"),
        ),
        sa.CheckConstraint(
            "asking_rent_monthly IS NULL OR asking_rent_monthly >= 0",
            name=op.f("ck_leasing_instructions_asking"),
        ),
        sa.CheckConstraint(
            "lease_start IS NULL OR lease_end IS NULL OR lease_end > lease_start",
            name=op.f("ck_leasing_instructions_dates"),
        ),
        sa.CheckConstraint(
            "security_deposit IS NULL OR security_deposit >= 0",
            name=op.f("ck_leasing_instructions_deposit"),
        ),
        sa.ForeignKeyConstraint(
            ["currency_id"],
            ["currencies.id"],
            name=op.f("fk_leasing_instructions_currency_id_currencies"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["owner_client_id", "project_id"],
            ["clients.id", "clients.project_id"],
            name="leasing_owner",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_leasing_instructions_project_id_projects"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["unit_id", "project_id"],
            ["units.id", "units.project_id"],
            name="leasing_unit",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_leasing_instructions")),
    )
    op.create_index(
        op.f("ix_leasing_instructions_project_id"),
        "leasing_instructions",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "uq_leasing_open_unit",
        "leasing_instructions",
        ["unit_id"],
        unique=True,
        postgresql_where=sa.text("NOT is_deleted AND status != 'closed'"),
    )


def downgrade() -> None:
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM leasing_instructions")):
        raise RuntimeError("Leasing history must be retained; downgrade refused.")
    op.drop_table("leasing_instructions")
