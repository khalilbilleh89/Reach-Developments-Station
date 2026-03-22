"""
app.core.calculation_engine

Centralized Calculation Engine — master platform engine for all derived
financial and operating formulas across the Reach Developments Station system.

Sub-modules
-----------
types     — Typed input/output dataclass contracts.
areas     — Area-based formulas (buildable, sellable, internal/attached).
pricing   — Pricing math (base price, premiums, escalation, discounts).
returns   — Return and profitability metrics (IRR, NPV, ROI, ROE, margin).
cashflow  — Cashflow and schedule math (aggregation, cumulative, deficit).
land      — Land underwriting formulas (land basis, residual land value).
registry  — Stable façade exposing canonical entry points.
"""
