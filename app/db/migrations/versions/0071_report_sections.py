"""Architect completion certificates and per-unit client charters in Reports."""

import sqlalchemy as sa
from alembic import op

revision = "0071_report_sections"
down_revision = "0070_operations_commissions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "project_site_reports",
        sa.Column("kind", sa.String(32), nullable=False, server_default="site_report"),
    )
    op.add_column("project_site_reports", sa.Column("building_id", sa.UUID(), nullable=True))
    op.add_column(
        "project_site_reports", sa.Column("building_label", sa.String(240), nullable=True)
    )
    op.alter_column("project_site_reports", "report_date", existing_type=sa.Date(), nullable=True)
    op.create_unique_constraint("report_project", "project_site_reports", ["id", "project_id"])
    op.create_foreign_key(
        "report_building",
        "project_site_reports",
        "buildings",
        ["building_id", "project_id"],
        ["id", "project_id"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        op.f("ck_project_site_reports_report_kind"),
        "project_site_reports",
        "kind IN ('site_report', 'architect_certificate', 'client_charter')",
    )
    op.create_check_constraint(
        op.f("ck_project_site_reports_site_report_fields"),
        "project_site_reports",
        "kind != 'site_report' OR (report_date IS NOT NULL AND building_id IS NULL)",
    )
    op.create_check_constraint(
        op.f("ck_project_site_reports_building_scope"),
        "project_site_reports",
        "kind = 'architect_certificate' OR building_id IS NULL",
    )
    op.create_table(
        "project_report_units",
        sa.Column("report_id", sa.UUID(), nullable=False),
        sa.Column("unit_id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("unit_label", sa.String(64), nullable=False),
        sa.PrimaryKeyConstraint("report_id", "unit_id", name="pk_project_report_units"),
        sa.ForeignKeyConstraint(
            ["report_id", "project_id"],
            ["project_site_reports.id", "project_site_reports.project_id"],
            name="report",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["unit_id", "project_id"],
            ["units.id", "units.project_id"],
            name="unit",
            ondelete="RESTRICT",
        ),
    )


def downgrade() -> None:
    if (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT EXISTS (SELECT 1 FROM project_site_reports WHERE kind != 'site_report')"
            )
        )
        .scalar()
    ):
        raise RuntimeError(
            "Certificates or charters exist; retain this migration and roll forward."
        )
    op.drop_table("project_report_units")
    for name in ("building_scope", "site_report_fields", "report_kind"):
        op.drop_constraint(
            op.f("ck_project_site_reports_" + name), "project_site_reports", type_="check"
        )
    op.drop_constraint("report_building", "project_site_reports", type_="foreignkey")
    op.drop_constraint("report_project", "project_site_reports", type_="unique")
    op.alter_column("project_site_reports", "report_date", existing_type=sa.Date(), nullable=False)
    for name in ("building_label", "building_id", "kind"):
        op.drop_column("project_site_reports", name)
