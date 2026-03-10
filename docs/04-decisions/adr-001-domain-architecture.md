# ADR-001: Domain Architecture — Modular Monolith with Asset-Backbone Centered Design

**Date:** 2026-03-10  
**Status:** Accepted  
**Decision By:** Development Director / Architecture Baseline

---

## Context

Reach Developments Station is being built as a Real Estate Development Operating System. The system spans multiple business domains (land, feasibility, pricing, sales, payment plans, collections, finance, registration) with complex inter-domain dependencies.

Before implementation begins, an architectural approach must be selected that:
- supports the operational complexity of a real estate developer
- is practical for solo or small-team execution
- enforces clean domain boundaries
- allows the system to evolve incrementally

---

## Decision

The system will be built as a **modular monolith**, not a microservices architecture.

The architecture will be **asset-backbone centered** — meaning all domain modules attach to the master hierarchy: `Project → Phase → Building → Floor → Unit`.

The repo will be **docs-first** — architecture documentation is the authoritative source of truth and must be maintained before and alongside implementation.

---

## Rationale

### Why modular monolith over microservices

| Factor | Modular Monolith | Microservices |
|---|---|---|
| Build complexity | Low | High |
| Operational overhead | Low | High (service discovery, distributed tracing, network contracts) |
| Refactoring cost | Low (in-process) | High (cross-service contracts) |
| Team size suitability | Solo / small team | Medium / large team |
| Data consistency | Strong (single DB) | Weak (eventual consistency) |
| Right time to adopt | Day one | When specific modules need independent scaling |

### Why asset-backbone centered design

Real estate development businesses are organized around their asset portfolio. Every commercial, financial, and governance activity relates back to a specific project, phase, building, or unit. Centering the architecture on this hierarchy reflects how the business actually operates and avoids artificial domain coupling.

### Why docs-first

The coding agent building this system does not have deep real estate domain intuition. Without detailed documentation, implementation risks include:
- collapsing unrelated domains into one module
- misunderstanding the difference between pricing, feasibility, and finance
- creating code structures that look organized but do not reflect actual developer operations

---

## Consequences

- All modules are deployed as a single application
- Database is shared (single PostgreSQL instance, scoped by module tables)
- Module boundaries are enforced through code structure, not network boundaries
- Future extraction to microservices is possible if a specific module needs independent scaling
- Architecture documentation must be kept current as implementation progresses
