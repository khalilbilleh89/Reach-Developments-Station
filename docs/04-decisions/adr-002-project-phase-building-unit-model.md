# ADR-002: Project → Phase → Building → Floor → Unit as System Backbone

**Date:** 2026-03-10  
**Status:** Accepted  
**Decision By:** Development Director / Architecture Baseline

---

## Context

A real estate development operating system must have a clear master data hierarchy that reflects how development businesses structure and track their portfolio. Without this, modules will have inconsistent ways of referencing assets, and reporting will be impossible to aggregate correctly.

Several possible backbone structures were considered:
1. Project → Unit (flat — loses building and floor granularity)
2. Project → Building → Unit (skips phase tracking)
3. Project → Phase → Unit (loses building and floor granularity)
4. Project → Phase → Building → Floor → Unit (full hierarchy)

---

## Decision

The system backbone is:

```
Project → Phase → Building → Floor → Unit
```

All downstream modules — pricing, sales, payment plans, collections, finance, registration — attach to one or more levels of this hierarchy.

---

## Rationale

### Why Phase is required

Real estate developments are typically delivered in phases. Phases have distinct delivery dates, unit inventories, and pricing. Collapsing phases into projects would make multi-phase development management impossible.

### Why Building is required

Large phases may contain multiple buildings. Building-level tracking is needed for construction progress, cost allocation, and delivery governance.

### Why Floor is required

Floor-level data is essential for:
- Premium rule application (floor-level pricing premiums)
- Unit mix reporting by floor
- Delivery governance (floor-by-floor handover)

### Why Unit is the atomic level

The unit (apartment, villa, townhouse, retail unit) is the fundamental sellable/leasable asset. All commercial activity (pricing, reservation, contract, payment, registration) occurs at the unit level.

---

## Consequences

- Every unit record has a traceable path: `Unit → Floor → Building → Phase → Project`
- Pricing, sales, payment plans, and collections all reference `unit_id` as their primary asset key
- Reporting can aggregate at any level: unit, floor, building, phase, or project
- The hierarchy must be maintained consistently — orphan records are not permitted
- This structure supports both simple projects (one phase, one building) and complex masterplans (many phases, many buildings)
