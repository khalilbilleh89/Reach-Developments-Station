# ADR-003: MVP Scope — What Is Built First

**Date:** 2026-03-10  
**Status:** Accepted  
**Decision By:** Development Director / Architecture Baseline

---

## Context

The full target architecture covers 18+ domain modules spanning the entire real estate development lifecycle. Building everything at once is impractical and risky.

A focused MVP scope must be defined to deliver a usable system early — one that creates real value for the business without overbuilding.

---

## Decision

The MVP consists of the following 12 modules:

| Module | Rationale |
|---|---|
| Projects | Asset backbone — must exist first |
| Phases | Asset backbone — must exist first |
| Buildings | Asset backbone — must exist first |
| Floors | Asset backbone — must exist first |
| Units | Asset backbone — must exist first |
| Land | Pre-development foundation — required for feasibility |
| Feasibility | Pre-development foundation — required before pricing |
| Pricing | Commercial backbone — required before sales |
| Sales | Commercial backbone — required before payment plans |
| Payment Plans | Finance backbone — required before collections |
| Collections | Finance backbone — required for financial visibility |
| Finance | Finance backbone — project financial summary |

---

## Deferred from MVP

| Module | Reason for Deferral |
|---|---|
| Concept Planning | Useful but not blocking core operations |
| Cost Planning & Tender | Important but complex — Phase 2 |
| Design & Delivery Governance | Phase 2 operational depth |
| Price Escalation | Extension of pricing — Phase 2 |
| Sales Exceptions & Incentives | Extension of sales — Phase 2 |
| Revenue Recognition (full) | Extension of finance — Phase 2 |
| Registration & Conveyancing | Post-sale — Phase 2 |
| Commissions | Post-sale finance — Phase 2 |
| Analytics | Requires data — Phase 3 |
| Market Intelligence | External data dependencies — Phase 3 |
| Document Intelligence | AI layer — Phase 3 |

---

## Rationale

The MVP modules cover the complete commercial and financial backbone: what assets exist, what they cost, who bought them, how they will pay, and whether they are paying. This is the minimum set needed to run commercial operations on the platform.

Deferred modules are not blocked — they can be built once the backbone is stable — but they are not required for initial usability.

---

## Consequences

- Developers can use the system from land acquisition through to financial summary in the MVP
- Feasibility, pricing, and sales are available before registration and analytics
- The build sequence within the MVP follows the logical dependency chain (backbone first, then commercial, then finance)
- Future modules attach cleanly to the established backbone
