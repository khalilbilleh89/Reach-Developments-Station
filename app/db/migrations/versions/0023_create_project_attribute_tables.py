"""create project attribute definition and option tables

Revision ID: 0023
Revises: 0022
Create Date: 2026-03-17

Adds two new tables that form the project-level attribute definition engine:

  project_attribute_definitions
    Each row represents a named, typed attribute set owned by a project
    (e.g. view_type for Project: Marina Residences).
    Unique constraint on (project_id, key) prevents duplicate keys per project
    regardless of is_active state.

  project_attribute_options
    Each row is an allowed selectable value within a definition
    (e.g. Sea View, Marina View, Internal View).
    Unique constraint on (definition_id, value) prevents duplicate option values.
    Unique constraint on (definition_id, label) prevents duplicate option labels.

Both tables are additive and non-breaking.
Referential integrity is enforced via CASCADE foreign keys.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0023"
down_revision: Union[str, None] = "0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "project_attribute_definitions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "project_id",
            sa.String(36),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("input_type", sa.String(50), nullable=False, server_default="select"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "key", name="uq_pad_project_key"),
    )
    op.create_index(
        "ix_project_attribute_definitions_project_id",
        "project_attribute_definitions",
        ["project_id"],
    )

    op.create_table(
        "project_attribute_options",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "definition_id",
            sa.String(36),
            sa.ForeignKey("project_attribute_definitions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("value", sa.String(255), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("definition_id", "value", name="uq_pao_definition_value"),
        sa.UniqueConstraint("definition_id", "label", name="uq_pao_definition_label"),
    )
    op.create_index(
        "ix_project_attribute_options_definition_id",
        "project_attribute_options",
        ["definition_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_project_attribute_options_definition_id",
        table_name="project_attribute_options",
    )
    op.drop_table("project_attribute_options")

    op.drop_index(
        "ix_project_attribute_definitions_project_id",
        table_name="project_attribute_definitions",
    )
    op.drop_table("project_attribute_definitions")
