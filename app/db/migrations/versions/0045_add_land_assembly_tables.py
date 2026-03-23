"""add land assembly tables

Revision ID: 0045
Revises: 0044
Create Date: 2026-03-23

PR-LAND-037 — Land Parcel Aggregation

Changes
-------
land_assemblies
  id                          VARCHAR(36)    PK (UUID)
  assembly_name               VARCHAR(255)   human-readable display name
  assembly_code               VARCHAR(100)   unique business code
  notes                       TEXT           optional developer notes
  status                      VARCHAR(50)    draft / under_review / approved / archived
  parcel_count                INTEGER        number of member parcels (snapshot)
  total_area_sqm              NUMERIC(14,2)  aggregated land area (snapshot)
  total_frontage_m            NUMERIC(12,2)  aggregated frontage (snapshot)
  total_acquisition_price     NUMERIC(20,2)  sum of parcel acquisition prices (snapshot)
  total_transaction_cost      NUMERIC(20,2)  sum of parcel transaction costs (snapshot)
  effective_land_basis        NUMERIC(20,2)  acquisition + transaction cost total (snapshot)
  weighted_permitted_far      NUMERIC(8,4)   area-weighted FAR (snapshot)
  dominant_zoning_category    VARCHAR(100)   most frequent zoning category (snapshot)
  mixed_zoning                BOOLEAN        True when > 1 zoning category (snapshot)
  has_utilities               BOOLEAN        True if any parcel has utilities (snapshot)
  has_corner_plot             BOOLEAN        True if any parcel is a corner plot (snapshot)
  assembly_results_json       JSON           full engine result snapshot
  created_at                  TIMESTAMP
  updated_at                  TIMESTAMP

land_assembly_parcels
  id                          VARCHAR(36)    PK (UUID)
  assembly_id                 VARCHAR(36)    FK → land_assemblies.id (CASCADE on delete)
  parcel_id                   VARCHAR(36)    FK → land_parcels.id (CASCADE on delete)
  notes                       TEXT           optional membership notes
  created_at                  TIMESTAMP
  updated_at                  TIMESTAMP

Indexes
-------
  land_assemblies(assembly_code)            UNIQUE
  land_assembly_parcels(assembly_id)
  land_assembly_parcels(parcel_id)          UNIQUE (one assembly per parcel)
  land_assembly_parcels(assembly_id, parcel_id)  UNIQUE
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0045"
down_revision: Union[str, None] = "0044"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "land_assemblies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("assembly_name", sa.String(255), nullable=False),
        sa.Column("assembly_code", sa.String(100), nullable=False, unique=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="draft"),
        # Aggregated snapshot fields
        sa.Column("parcel_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_area_sqm", sa.Numeric(14, 2), nullable=True),
        sa.Column("total_frontage_m", sa.Numeric(12, 2), nullable=True),
        sa.Column("total_acquisition_price", sa.Numeric(20, 2), nullable=True),
        sa.Column("total_transaction_cost", sa.Numeric(20, 2), nullable=True),
        sa.Column("effective_land_basis", sa.Numeric(20, 2), nullable=True),
        sa.Column("weighted_permitted_far", sa.Numeric(8, 4), nullable=True),
        sa.Column("dominant_zoning_category", sa.String(100), nullable=True),
        sa.Column("mixed_zoning", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("has_utilities", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("has_corner_plot", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("assembly_results_json", sa.JSON, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "land_assembly_parcels",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "assembly_id",
            sa.String(36),
            sa.ForeignKey("land_assemblies.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "parcel_id",
            sa.String(36),
            sa.ForeignKey("land_parcels.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("assembly_id", "parcel_id", name="uq_assembly_parcel"),
        sa.UniqueConstraint("parcel_id", name="uq_parcel_single_assembly"),
    )


def downgrade() -> None:
    op.drop_table("land_assembly_parcels")
    op.drop_table("land_assemblies")
