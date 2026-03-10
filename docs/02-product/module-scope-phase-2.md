# Module Scope — Phase 2

## Purpose

This document defines the scope of Phase 2 modules — the operational depth layer that extends the MVP backbone with pre-development planning, delivery governance, cost control, pricing escalation, sales exception governance, and post-sale operations.

Phase 2 begins after the MVP backbone is stable and in use.

---

## Phase 2 Modules

### 1. Concept Planning

**What is built:**
- Development scenario creation (unit mix, density, GFA)
- Unit mix engine (bedroom type, count, average area, price assumptions)
- Scenario comparison
- GDV estimation from unit mix

**Dependencies:** Projects, Phases, Feasibility (MVP)

---

### 2. Cost Planning & Tender

**What is built:**
- Cost plan creation per project/phase
- Cost line management (category, subcategory, quantity, unit rate, amount)
- Tender package management (scope, issue date, submissions)
- Tender comparison engine
- Cost variance tracking (budget vs. actual)

**Dependencies:** Projects, Phases, Buildings (MVP)

---

### 3. Design & Delivery Governance

**What is built:**
- Stage gate definition per phase
- Stage gate approval workflow (document upload, sign-off)
- Permit tracker (permit type, status, submission date, approval date)
- Consultant register and coordination log

**Dependencies:** Projects, Phases, Buildings (MVP)

---

### 4. Price Escalation

**What is built:**
- Escalation event definition (trigger type: sales milestone, date, construction milestone)
- Escalation percentage or fixed amount per event
- Escalation approval workflow
- Price list update on escalation trigger

**Dependencies:** Pricing (MVP)

---

### 5. Sales Exceptions & Incentives

**What is built:**
- Discount request workflow (requested by Sales, approved by Sales Manager / Director / CEO based on threshold)
- Incentive management (type: free parking, furniture package, extended payment plan)
- Exception log per contract
- Exception impact reporting

**Dependencies:** Sales (MVP)

---

### 6. Revenue Recognition (Full)

**What is built:**
- Stage-based recognition (percentage of completion method)
- Milestone-based recognition (recognition triggered by defined events)
- Deferred revenue schedule
- Revenue recognition reporting per project

**Dependencies:** Sales, Payment Plans, Collections (MVP)

---

### 7. Registration & Conveyancing

**What is built:**
- Registration case creation per contract
- Document checklist management (document type, status, upload, approval)
- Workflow status tracking (initiated → docs submitted → submitted to authority → title issued)
- Title deed record

**Dependencies:** Sales (MVP)

---

### 8. Commissions

**What is built:**
- Agent / broker registry
- Commission agreement per contract (rate or fixed amount)
- Commission payable tracking
- Commission payment recording

**Dependencies:** Sales (MVP)

---

## Phase 2 Build Sequence

Recommended order:

1. Concept Planning (logical extension of Feasibility)
2. Cost Planning & Tender (completes pre-development picture)
3. Design & Delivery Governance (enables delivery tracking)
4. Price Escalation (extends Pricing)
5. Sales Exceptions & Incentives (extends Sales)
6. Revenue Recognition (full) (extends Finance)
7. Registration & Conveyancing (post-sale workflow)
8. Commissions (post-sale finance)

---

## Explicitly Deferred from Phase 2

| Module | Deferred To |
|---|---|
| Analytics | Phase 3 |
| Market Intelligence | Phase 3 |
| Document Intelligence | Phase 3 |
