# Core Data Model

## Overview

This document defines the conceptual data backbone for Reach Developments Station. It describes the core entities, their relationships, and the grouping of entities by domain layer.

This is a **conceptual model** — not a SQL schema or migration file. Database implementation details are in [`../03-technical/database-architecture.md`](../03-technical/database-architecture.md).

---

## Core Entities

### Asset Backbone Entities

These entities form the structural foundation of the entire system:

| Entity | Key Attributes | Relationships |
|---|---|---|
| **Project** | name, code, type, status, location, start_date, completion_date | Has many Phases, Land parcels, Feasibility scenarios |
| **Phase** | name, code, project_id, status, delivery_date, unit_count | Belongs to Project; has many Buildings |
| **Building** | name, code, phase_id, type, floor_count, unit_count | Belongs to Phase; has many Floors |
| **Floor** | number, building_id, unit_count | Belongs to Building; has many Units |
| **Unit** | unit_number, floor_id, type, bedrooms, area_gross, area_net, area_balcony, status, current_price | Belongs to Floor; linked to Pricing, Sales, Registration |

---

## Upstream Domain Entities

### Land

| Entity | Key Attributes |
|---|---|
| **LandParcel** | project_id, area_sqm, location, acquisition_cost, acquisition_date, ownership_status |
| **LandValuation** | parcel_id, valuation_date, market_value, residual_value, methodology |
| **LandCost** | parcel_id, cost_type, amount, date |

### Concept Planning

| Entity | Key Attributes |
|---|---|
| **ConceptScenario** | project_id, name, total_units, unit_mix_definition, density, gfa |
| **UnitMixLine** | scenario_id, unit_type, count, avg_area, avg_price_assumption |

### Feasibility

| Entity | Key Attributes |
|---|---|
| **FeasibilityScenario** | project_id, name, status, created_at |
| **FeasibilityAssumption** | scenario_id, category, label, value, unit |
| **FeasibilityResult** | scenario_id, total_revenue, total_cost, gross_profit, gross_margin, irr, npv, break_even_units |
| **CashflowPeriod** | scenario_id, period, inflow, outflow, net, cumulative |

### Cost Planning

| Entity | Key Attributes |
|---|---|
| **CostPlan** | project_id, phase_id, version, status |
| **CostLine** | plan_id, category, subcategory, description, quantity, unit, unit_rate, amount |
| **TenderPackage** | phase_id, scope, status, issue_date, award_date |
| **TenderSubmission** | package_id, contractor_name, amount, notes |

---

## Commercial Domain Entities

### Pricing

| Entity | Key Attributes |
|---|---|
| **PriceList** | phase_id, name, effective_date, status |
| **UnitPrice** | unit_id, price_list_id, base_price, premium_adjustments, final_price |
| **PremiumRule** | price_list_id, rule_type, condition, adjustment_type, adjustment_value |
| **PriceOverride** | unit_id, requested_price, reason, requested_by, approved_by, status |
| **EscalationEvent** | price_list_id, trigger_type, trigger_condition, escalation_percent, effective_date |

### Sales

| Entity | Key Attributes |
|---|---|
| **Customer** | name, email, phone, id_number, nationality |
| **Reservation** | unit_id, customer_id, date, amount, expiry_date, status |
| **SalesContract** | reservation_id, unit_id, customer_id, contract_date, agreed_price, status |
| **SalesException** | contract_id, exception_type, requested_discount, reason, approval_status, approved_by |
| **Incentive** | contract_id, incentive_type, value, approved_by |

---

## Finance Domain Entities

### Payment Plans

| Entity | Key Attributes |
|---|---|
| **PaymentPlanTemplate** | name, description, structure_type, total_milestones |
| **PaymentPlanMilestone** | template_id, sequence, label, trigger_type, trigger_condition, percentage |
| **ContractPaymentPlan** | contract_id, template_id, agreed_price, generated_at |
| **PaymentScheduleLine** | plan_id, milestone_label, due_date, amount, status |

### Collections & Receivables

| Entity | Key Attributes |
|---|---|
| **PaymentReceipt** | contract_id, receipt_date, amount, payment_method, reference |
| **ReceiptAllocation** | receipt_id, schedule_line_id, allocated_amount |
| **AgingBucket** | contract_id, current_balance, 30d_overdue, 60d_overdue, 90d_overdue, 90plus_overdue |
| **CollectionAlert** | contract_id, alert_type, severity, raised_at, resolved_at |

### Revenue Recognition

| Entity | Key Attributes |
|---|---|
| **RevenueEvent** | contract_id, recognition_date, amount, trigger, method |
| **RevenueSchedule** | contract_id, total_contract_value, recognized_to_date, deferred |

### Finance Summary

| Entity | Key Attributes |
|---|---|
| **ProjectFinancialSummary** | project_id, period, total_contracted_revenue, collected_revenue, outstanding_receivables, total_cost, net_margin |

---

## Post-Sale Domain Entities

### Registration & Conveyancing

| Entity | Key Attributes |
|---|---|
| **RegistrationCase** | contract_id, unit_id, customer_id, status, initiated_date, completion_date |
| **RegistrationDocument** | case_id, document_type, status, uploaded_at, approved_at |
| **TitleDeed** | registration_case_id, deed_number, issued_date |

### Commissions

| Entity | Key Attributes |
|---|---|
| **Agent** | name, agency_name, license_number, contact |
| **CommissionAgreement** | contract_id, agent_id, rate_percent, agreed_amount |
| **CommissionPayable** | agreement_id, amount, due_date, paid_date, status |

---

## Support Entities

| Entity | Purpose |
|---|---|
| **User** | Platform user accounts |
| **Role** | User role definitions (RBAC) |
| **Permission** | Granular permission assignments |
| **AuditLog** | Immutable record of all create/update/delete operations |
| **Document** | Attached files and documents across all modules |
| **Notification** | System-generated alerts and messages |
