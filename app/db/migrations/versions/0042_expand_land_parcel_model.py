"""expand land parcel model

Revision ID: 0042
Revises: 0041
Create Date: 2026-03-22

PR-LAND-001 — Land Data Model Expansion

Adds underwriting-ready fields to land_parcels so the platform can support
real developer underwriting rather than just parcel registration.

New columns added to land_parcels
----------------------------------
Identity & cadastral reference:
  plot_number         VARCHAR(100)  — cadastral plot reference number
  cadastral_id        VARCHAR(100)  — formal cadastral identifier
  title_reference     VARCHAR(255)  — legal title / deed reference
  location_link       VARCHAR(1000) — map/GIS URL for the parcel
  municipality        VARCHAR(100)  — municipality name
  submarket           VARCHAR(100)  — submarket / micro-location area

Physical / dimensional attributes:
  buildable_area_sqm  NUMERIC(12,2) — permitted buildable area per zoning
  sellable_area_sqm   NUMERIC(12,2) — estimated sellable area
  coverage_ratio      NUMERIC(6,4)  — permitted site coverage ratio (0–1)
  density_ratio       NUMERIC(8,4)  — density ratio (GFA / land area)
  front_setback_m     NUMERIC(8,2)  — front setback in metres
  side_setback_m      NUMERIC(8,2)  — side setback in metres
  rear_setback_m      NUMERIC(8,2)  — rear setback in metres
  access_notes        TEXT          — notes on road/site access
  utilities_notes     TEXT          — notes on available utilities

Acquisition economics:
  acquisition_price       NUMERIC(20,2) — agreed / target acquisition price
  transaction_cost        NUMERIC(20,2) — estimated transaction costs (fees, taxes)
  currency                VARCHAR(10)   — ISO currency code (e.g. AED, USD)
  asking_price_per_sqm    NUMERIC(14,2) — vendor asking price per sqm
  supported_price_per_sqm NUMERIC(14,2) — residual-supported price per sqm

Governance / provenance:
  assumption_notes  TEXT — notes on key modelling assumptions
  source_notes      TEXT — data provenance / source of parcel information
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0042"
down_revision: Union[str, None] = "0041"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("land_parcels") as batch_op:
        # Identity & cadastral reference
        batch_op.add_column(sa.Column("plot_number", sa.String(100), nullable=True))
        batch_op.add_column(sa.Column("cadastral_id", sa.String(100), nullable=True))
        batch_op.add_column(sa.Column("title_reference", sa.String(255), nullable=True))
        batch_op.add_column(sa.Column("location_link", sa.String(1000), nullable=True))
        batch_op.add_column(sa.Column("municipality", sa.String(100), nullable=True))
        batch_op.add_column(sa.Column("submarket", sa.String(100), nullable=True))

        # Physical / dimensional attributes
        batch_op.add_column(sa.Column("buildable_area_sqm", sa.Numeric(12, 2), nullable=True))
        batch_op.add_column(sa.Column("sellable_area_sqm", sa.Numeric(12, 2), nullable=True))
        batch_op.add_column(sa.Column("coverage_ratio", sa.Numeric(6, 4), nullable=True))
        batch_op.add_column(sa.Column("density_ratio", sa.Numeric(8, 4), nullable=True))
        batch_op.add_column(sa.Column("front_setback_m", sa.Numeric(8, 2), nullable=True))
        batch_op.add_column(sa.Column("side_setback_m", sa.Numeric(8, 2), nullable=True))
        batch_op.add_column(sa.Column("rear_setback_m", sa.Numeric(8, 2), nullable=True))
        batch_op.add_column(sa.Column("access_notes", sa.Text, nullable=True))
        batch_op.add_column(sa.Column("utilities_notes", sa.Text, nullable=True))

        # Acquisition economics
        batch_op.add_column(sa.Column("acquisition_price", sa.Numeric(20, 2), nullable=True))
        batch_op.add_column(sa.Column("transaction_cost", sa.Numeric(20, 2), nullable=True))
        batch_op.add_column(sa.Column("currency", sa.String(10), nullable=True))
        batch_op.add_column(sa.Column("asking_price_per_sqm", sa.Numeric(14, 2), nullable=True))
        batch_op.add_column(sa.Column("supported_price_per_sqm", sa.Numeric(14, 2), nullable=True))

        # Governance / provenance
        batch_op.add_column(sa.Column("assumption_notes", sa.Text, nullable=True))
        batch_op.add_column(sa.Column("source_notes", sa.Text, nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("land_parcels") as batch_op:
        # Governance / provenance
        batch_op.drop_column("source_notes")
        batch_op.drop_column("assumption_notes")

        # Acquisition economics
        batch_op.drop_column("supported_price_per_sqm")
        batch_op.drop_column("asking_price_per_sqm")
        batch_op.drop_column("currency")
        batch_op.drop_column("transaction_cost")
        batch_op.drop_column("acquisition_price")

        # Physical / dimensional attributes
        batch_op.drop_column("utilities_notes")
        batch_op.drop_column("access_notes")
        batch_op.drop_column("rear_setback_m")
        batch_op.drop_column("side_setback_m")
        batch_op.drop_column("front_setback_m")
        batch_op.drop_column("density_ratio")
        batch_op.drop_column("coverage_ratio")
        batch_op.drop_column("sellable_area_sqm")
        batch_op.drop_column("buildable_area_sqm")

        # Identity & cadastral reference
        batch_op.drop_column("submarket")
        batch_op.drop_column("municipality")
        batch_op.drop_column("location_link")
        batch_op.drop_column("title_reference")
        batch_op.drop_column("cadastral_id")
        batch_op.drop_column("plot_number")
