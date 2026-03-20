# Reach Developments Station — Production Contradictions Register

**Generated:** 2026-03-20  
**Source:** [PLATFORM_TRUTH_AUDIT.md](PLATFORM_TRUTH_AUDIT.md)

---

## Purpose

This register documents every identified contradiction between the repository implementation and production behavior. Each entry is supported by source code evidence. Production environment was not directly accessible during this audit; contradictions are inferred from code analysis and prior audit reports.

---

## Contradiction #1 — Commission Page Shows Demo Banner

| Field | Value |
|-------|-------|
| **Area** | Commission frontend |
| **Contradiction** | Commission page renders "⬡ Demo Preview — static data only" banner and displays hardcoded commission data. Backend has a fully implemented commission service (577 lines, 22 methods) with marginal/cumulative slab calculation, payout audit trail, and 10 API endpoints. |
| **Evidence** | `frontend/src/app/(protected)/commission/page.tsx:33` — demo banner div; imports `demoCommissionRows` from `demo-data.ts`; does NOT import or call `commission-api.ts` |
| **Backend evidence** | `app/modules/commission/service.py` — 577 lines of real calculation logic; `app/modules/commission/api.py` — 10 endpoints |
| **Likely cause** | **Stubbed frontend** — frontend page was never wired to backend API; demo data was used as a UI placeholder during development |
| **Impact** | Users see static AED commission data that does not reflect real contract values or commission calculations |

---

## Contradiction #2 — Cashflow Page Shows Demo Banner

| Field | Value |
|-------|-------|
| **Area** | Cashflow frontend |
| **Contradiction** | Cashflow page renders "⬡ Demo Preview — static data only" banner and displays hardcoded monthly cashflow periods. Backend has a fully implemented cashflow service (357 lines, 10 methods) with 3 forecast modes and 5 API endpoints. |
| **Evidence** | `frontend/src/app/(protected)/cashflow/page.tsx:18` — demo banner div; imports `demoCashflowPeriods` from `demo-data.ts`; does NOT call cashflow API |
| **Backend evidence** | `app/modules/cashflow/service.py` — 357 lines with scheduled_collections, actual_plus_scheduled, blended modes; `app/modules/cashflow/api.py` — 5 endpoints |
| **Likely cause** | **Stubbed frontend** — cashflow page was never wired to backend API |
| **Impact** | Users see static AED cashflow data (Oct 2025–Mar 2026) that does not reflect real payment schedules or collection activity |

---

## Contradiction #3 — Settings Page Shows Hardcoded Organization Data

| Field | Value |
|-------|-------|
| **Area** | Settings frontend |
| **Contradiction** | Settings page displays hardcoded organization settings (company name, currency, region). Backend has 15 fully implemented settings endpoints for pricing policies, commission policies, and project templates. Frontend has `settings-api.ts` wrapper file but it is not called by the page. |
| **Evidence** | `frontend/src/app/(protected)/settings/page.tsx:93` — "INTENTIONAL DEMO DATA" comment; inline hardcoded values; `frontend/src/lib/settings-api.ts` exists but unused by page |
| **Backend evidence** | `app/modules/settings/api.py` — 15 endpoints; `app/modules/settings/service.py` — 321 lines |
| **Likely cause** | **Stubbed frontend** — settings page was built with placeholder data; API wrapper exists but was never integrated |
| **Impact** | Users cannot manage pricing policies, commission policies, or project templates through the UI |

---

## Contradiction #4 — Land Domain Not Visible in Production UI

| Field | Value |
|-------|-------|
| **Area** | Land frontend / navigation |
| **Contradiction** | Land domain has 8 backend API endpoints, 3 data models (LandParcel, LandAssumptions, LandValuation), and real business logic in the service layer (185 lines). However, there is no frontend page for Land and it is not listed in the sidebar navigation. |
| **Evidence** | `frontend/src/lib/NavConfig.ts` — Land is not in NAV_ITEMS array; no directory exists at `frontend/src/app/(protected)/land/`; no `land-api.ts` wrapper exists |
| **Backend evidence** | `app/modules/land/api.py` — 8 endpoints; `app/modules/land/service.py` — 185 lines with GDV and RLV calculation |
| **Likely cause** | **Missing frontend** — Land frontend pages were never built; domain is backend-only |
| **Impact** | Land intelligence is inaccessible to users; parcel management requires direct API calls |

---

## Contradiction #5 — Feasibility Domain Not Visible in Production UI

| Field | Value |
|-------|-------|
| **Area** | Feasibility frontend / navigation |
| **Contradiction** | Feasibility domain has 8 backend API endpoints, 3 data models, a fully implemented calculation engine (151 lines with dataclasses), and service coordination. However, there is no frontend page and it is not in sidebar navigation. |
| **Evidence** | `frontend/src/lib/NavConfig.ts` — Feasibility is not in NAV_ITEMS array; no directory at `frontend/src/app/(protected)/feasibility/`; no `feasibility-api.ts` wrapper |
| **Backend evidence** | `app/modules/feasibility/engines/feasibility_engine.py` — 151 lines; 9 calculation functions; called by service |
| **Likely cause** | **Missing frontend** — Feasibility pages never built; domain is backend-only |
| **Impact** | Feasibility studies and proforma analysis are inaccessible to users; requires direct API calls |

---

## Contradiction #6 — Finance Dashboard May Show Zero Monetary Values

| Field | Value |
|-------|-------|
| **Area** | Finance dashboard |
| **Contradiction** | Prior audit reports indicate the Finance screen shows sold units but zero monetary values. The finance service aggregates from contracts and collections — if no contracts or receipts exist in the production database, all financial summaries return zero legitimately. |
| **Evidence** | `app/modules/finance/service.py:30-83` — `get_project_summary()` sums `SalesContract.contract_price` and `PaymentReceipt.amount_received`; returns 0.0 when no records exist |
| **Likely cause** | **Bad seed data or missing data** — production may not have contracts/receipts for the displayed project, or seed data was incomplete |
| **Impact** | Finance dashboard appears broken (zero values) even though the code is correct — it accurately reflects empty data |

---

## Contradiction #7 — Currency Handling Inconsistency

| Field | Value |
|-------|-------|
| **Area** | Currency model / cross-domain |
| **Contradiction** | Currency is stored per-record in some models (UnitPricing.currency, UnitReservation.currency, Receivable.currency, ConstructionCostItem.currency) but not at the Project level. Demo data hardcodes "AED" throughout. There is no currency conversion logic anywhere in the codebase. |
| **Evidence** | `app/modules/projects/models.py` — Project model has NO currency field; `app/modules/pricing/models.py` — UnitPricing has `currency` column; `frontend/src/lib/demo-data.ts` — all values use "AED" |
| **Likely cause** | **Inconsistent design** — currency was added per-record during domain development but never unified at the project level |
| **Impact** | Multi-currency projects are structurally unsupported; analytics cannot reliably aggregate monetary values across domains; reporting assumes single currency |

---

## Summary

| # | Area | Type | Severity |
|---|------|------|----------|
| 1 | Commission | Stubbed frontend | High — fully built backend wasted |
| 2 | Cashflow | Stubbed frontend | High — fully built backend wasted |
| 3 | Settings | Stubbed frontend | Medium — management features inaccessible |
| 4 | Land | Missing frontend | Medium — domain invisible to users |
| 5 | Feasibility | Missing frontend | Medium — domain invisible to users |
| 6 | Finance | Bad/missing data | Medium — appears broken but code is correct |
| 7 | Currency | Inconsistent design | High — blocks multi-currency and reliable analytics |
