"""
app.core.calculation_engine.land

Centralized land underwriting formulas.

Covers:
- Land price per sqm (acquisition basis).
- Land price per buildable sqm.
- Land price per sellable sqm.
- Residual Land Value (RLV).
- Maximum supported acquisition price.
- Margin impact of the land basis.

No cadastral lookups, parcel CRUD, or zoning authority integration belongs here.
"""

from __future__ import annotations

from app.core.calculation_engine.types import LandInputs, LandOutputs


# ---------------------------------------------------------------------------
# Pure formula functions
# ---------------------------------------------------------------------------


def calculate_land_price_per_sqm(
    acquisition_price: float,
    land_area_sqm: float,
) -> float:
    """Land price per gross sqm = acquisition price / land area.

    Returns 0.0 when land area is zero.
    """
    if land_area_sqm <= 0.0:
        return 0.0
    return acquisition_price / land_area_sqm


def calculate_land_price_per_buildable_sqm(
    acquisition_price: float,
    buildable_area_sqm: float,
) -> float:
    """Land price per buildable sqm = acquisition price / buildable area.

    Returns 0.0 when buildable area is zero.
    """
    if buildable_area_sqm <= 0.0:
        return 0.0
    return acquisition_price / buildable_area_sqm


def calculate_land_price_per_sellable_sqm(
    acquisition_price: float,
    sellable_area_sqm: float,
) -> float:
    """Land price per sellable sqm = acquisition price / sellable area.

    Returns 0.0 when sellable area is zero.
    """
    if sellable_area_sqm <= 0.0:
        return 0.0
    return acquisition_price / sellable_area_sqm


def calculate_residual_land_value(
    gdv: float,
    total_development_cost: float,
    developer_margin_target: float,
) -> float:
    """Residual Land Value = GDV − total development cost − target profit.

    RLV represents the maximum amount a developer can pay for land while
    achieving the target developer margin.

    The result may be negative when development economics do not support
    a positive land residual — callers should surface this condition.

    Parameters
    ----------
    gdv:
        Gross Development Value (total revenue from sales).
    total_development_cost:
        Total cost of development excluding land acquisition.
    developer_margin_target:
        Target developer profit margin as a decimal fraction
        (e.g. 0.20 for 20 % of GDV).
    """
    target_profit = gdv * developer_margin_target
    return gdv - total_development_cost - target_profit


def calculate_margin_impact(residual_land_value: float, gdv: float) -> float:
    """Margin impact = residual land value / GDV.

    Expresses the land value as a fraction of gross revenue.
    Returns 0.0 when GDV is zero.
    """
    if gdv <= 0.0:
        return 0.0
    return residual_land_value / gdv


# ---------------------------------------------------------------------------
# Composite runner
# ---------------------------------------------------------------------------


def run_land_calculations(inputs: LandInputs) -> LandOutputs:
    """Compute the full set of land underwriting metrics from structured inputs.

    Parameters
    ----------
    inputs:
        Validated :class:`~app.core.calculation_engine.types.LandInputs`.

    Returns
    -------
    LandOutputs
        All derived land underwriting metrics.
    """
    land_price_per_sqm = calculate_land_price_per_sqm(
        inputs.acquisition_price, inputs.land_area_sqm
    )
    land_price_per_buildable_sqm = calculate_land_price_per_buildable_sqm(
        inputs.acquisition_price, inputs.buildable_area_sqm
    )
    land_price_per_sellable_sqm = calculate_land_price_per_sellable_sqm(
        inputs.acquisition_price, inputs.sellable_area_sqm
    )
    rlv = calculate_residual_land_value(
        inputs.gdv,
        inputs.total_development_cost,
        inputs.developer_margin_target,
    )
    margin_impact = calculate_margin_impact(rlv, inputs.gdv)

    return LandOutputs(
        land_price_per_sqm=land_price_per_sqm,
        land_price_per_buildable_sqm=land_price_per_buildable_sqm,
        land_price_per_sellable_sqm=land_price_per_sellable_sqm,
        residual_land_value=rlv,
        max_supported_acquisition_price=rlv,
        margin_impact=margin_impact,
    )
