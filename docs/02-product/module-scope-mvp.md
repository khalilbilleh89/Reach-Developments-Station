# Module Scope — MVP

## Purpose

This document defines the exact scope of the MVP (Minimum Viable Product) build. It specifies which modules are included, what must be built within each module, and what is explicitly deferred.

The MVP is designed to deliver a working development-commercial-finance backbone that a real estate developer can use to manage their portfolio from unit registration through to financial summary.

---

## MVP Modules

### 1. Projects

**What is built:**
- Project CRUD (create, read, update, delete)
- Project attributes: name, code, type, status, location, start_date, completion_date
- Project status management (Pipeline → Active → Completed)

**Deferred:**
- External data integrations
- Advanced portfolio analytics

---

### 2. Phases

**What is built:**
- Phase CRUD
- Phase attributes: name, code, project reference, status, delivery_date, unit_count
- Phase status management

**Deferred:**
- Construction milestone integration
- Automated phase status updates from delivery governance

---

### 3. Buildings

**What is built:**
- Building CRUD
- Building attributes: name, code, phase reference, type, floor_count, unit_count

**Deferred:**
- Building-level cost allocation
- Building permit tracking (Phase 2)

---

### 4. Floors

**What is built:**
- Floor CRUD
- Floor attributes: floor number, building reference, unit_count

**Deferred:**
- Floor plan document attachment (Phase 3)

---

### 5. Units

**What is built:**
- Unit CRUD
- Unit attributes: unit number, floor reference, type, bedrooms, area_gross, area_net, area_balcony, status, current_price
- Unit status management: Available → Reserved → Under Contract → Registered
- Pricing adapter (reads active price from Pricing module)
- Unit status rules (enforces valid status transitions)

**Deferred:**
- Unit-level document management
- Handover checklist

---

### 6. Land

**What is built:**
- Land parcel registration
- Acquisition cost and date recording
- Basic residual land value calculator (inputs: GDV, total costs, target margin)
- Land cost export to Feasibility

**Deferred:**
- Advanced valuation methodologies
- Multi-parcel assembly logic

---

### 7. Feasibility

**What is built:**
- Feasibility scenario creation (per project)
- Revenue assumption inputs (unit count, area, price per sqm by type)
- Cost assumption inputs (land, construction, professional fees, selling costs, finance costs, contingency)
- Cashflow timing assumptions
- Calculated outputs: GDV, total cost, gross profit, gross margin, IRR, NPV, break-even units
- Scenario comparison (multiple scenarios per project)
- Scenario approval workflow

**Deferred:**
- Monte Carlo sensitivity simulation
- Market comparable data integration

---

### 8. Pricing

**What is built:**
- Price list creation and management per phase
- Base price assignment per unit
- Premium rule engine (floor, view, corner, orientation premiums)
- Price list versioning and activation
- Price override request and approval workflow

**Deferred:**
- Price escalation (Phase 2 — separate module)
- Bulk pricing import from external spreadsheet

---

### 9. Sales

**What is built:**
- Customer registration
- Unit reservation (with expiry logic)
- Sales contract creation and management
- Reservation-to-contract conversion
- Sales pipeline view

**Deferred:**
- Sales exceptions and incentives (Phase 2 — separate module)
- External CRM integration
- Agent portal

---

### 10. Payment Plans

**What is built:**
- Payment plan template library
- Template milestone definition (trigger type, percentage, label)
- Contract payment plan assignment
- Payment schedule generation (dates and amounts per contract)
- Basic cashflow projection from schedule portfolio

**Deferred:**
- Complex post-handover plan restructuring
- External payment gateway integration

---

### 11. Collections

**What is built:**
- Payment receipt recording
- Receipt-to-schedule-line matching
- Aging analysis (current, 30, 60, 90, 90+ days)
- Collection alerts (7-day and 30-day overdue triggers)
- Outstanding receivables report

**Deferred:**
- Legal escalation workflow
- Late payment penalty calculation

---

### 12. Finance

**What is built:**
- Revenue recognition tracking (milestone-based)
- Project financial summary (contracted revenue, collected, outstanding, cost, margin)
- Cashflow forecast (from payment schedule portfolio)

**Deferred:**
- Full P&L reporting
- Multi-currency support
- External accounting system integration

---

## Explicitly Deferred from MVP

The following modules are **not** built in the MVP:

| Module | Deferred To |
|---|---|
| Concept Planning | Phase 2 |
| Cost Planning & Tender | Phase 2 |
| Design & Delivery Governance | Phase 2 |
| Price Escalation | Phase 2 |
| Sales Exceptions & Incentives | Phase 2 |
| Revenue Recognition (full) | Phase 2 |
| Registration & Conveyancing | Phase 2 |
| Commissions | Phase 2 |
| Analytics | Phase 3 |
| Market Intelligence | Phase 3 |
| Document Intelligence | Phase 3 |
