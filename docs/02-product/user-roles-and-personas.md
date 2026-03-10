# User Roles and Personas

## Overview

Reach Developments Station uses a Role-Based Access Control (RBAC) model. Each user is assigned one or more roles that determine which modules they can access and what actions they can perform within those modules.

---

## Roles

### Development Director / CEO

**Primary responsibilities:**
- Portfolio-level oversight and strategic decision-making
- Feasibility and pricing sign-off
- Escalated exception approvals (discounts above Sales Manager threshold)

**Key system access:**
- All modules read access
- Feasibility approval
- Price list approval
- Sales exception approval (all levels)
- Project and phase configuration

---

### Project Manager

**Primary responsibilities:**
- Phase and building progress management
- Delivery governance tracking
- Cost planning oversight

**Key system access:**
- Projects, Phases, Buildings, Floors read/write
- Design & Delivery Governance full access
- Cost Planning read access
- Land read access

---

### Feasibility Analyst

**Primary responsibilities:**
- Development proforma modelling
- Scenario comparison and sensitivity analysis
- Residual land value calculation

**Key system access:**
- Feasibility full access
- Land read/write
- Concept Planning full access
- Projects and Phases read access

---

### Pricing Manager

**Primary responsibilities:**
- Price list creation and management
- Premium rule configuration
- Price escalation management
- Override request review

**Key system access:**
- Pricing full access
- Price Escalation full access
- Units read access
- Sales Exceptions (pricing-related) read access

---

### Sales Manager

**Primary responsibilities:**
- Sales pipeline management
- Reservation and contract oversight
- Exception approvals within threshold (≤2% discount)
- Sales team performance monitoring

**Key system access:**
- Sales full access
- Reservations full access
- Sales Exceptions full access (within threshold)
- Units read access
- Pricing read access
- Commissions read access

---

### Finance Manager

**Primary responsibilities:**
- Payment plan governance
- Collections portfolio oversight
- Revenue recognition reporting
- Project financial summary review

**Key system access:**
- Payment Plans full access
- Collections read/write
- Revenue Recognition full access
- Finance Summary full access
- Sales read access

---

### Collections Officer

**Primary responsibilities:**
- Day-to-day receivables management
- Receipt recording and matching
- Overdue account follow-up
- Alert resolution

**Key system access:**
- Collections full access
- Payment Plans read access
- Sales read access

---

### Registration Officer

**Primary responsibilities:**
- Title transfer workflow management
- Document checklist governance
- Regulatory submission coordination

**Key system access:**
- Registration full access
- Sales read access
- Units read access

---

## Permission Levels

| Action | Permission Required |
|---|---|
| View records | `read` |
| Create / edit records | `write` |
| Approve / reject decisions | `approve` |
| Delete records | `delete` (restricted to admins) |
| Configure system settings | `admin` |

---

## Future Roles (Phase 2 / 3)

| Role | Purpose |
|---|---|
| Market Intelligence Analyst | Market data input and benchmark management |
| Document Intelligence Operator | Document ingestion and extraction review |
| External Agent (Broker) | Limited access portal for commission tracking |
