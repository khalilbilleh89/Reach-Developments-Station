# Workflows

## Overview

This document describes the key end-to-end workflows that span multiple modules. These cross-module workflows are the most important to understand before implementation begins because they define the integration contracts between modules.

---

## Workflow 1 — Pre-Development to Pricing

```
Land Registration
    ↓
Concept Planning (unit mix, GFA, density)
    ↓
Feasibility Modelling (proforma, IRR, NPV)
    ↓
Feasibility Approval (Development Director)
    ↓
Unit Registry Setup (Buildings, Floors, Units)
    ↓
Pricing (price list, premium rules, activation)
    ↓
Units Available for Sale
```

---

## Workflow 2 — Reservation to Contract

```
Customer Registration
    ↓
Unit Availability Check
    ↓
Reservation Created (unit status → Reserved)
    ↓
Reservation Deposit Collected
    ↓
Contract Preparation (SPA)
    ↓
Contract Signed (unit status → Under Contract)
    ↓
Payment Plan Assigned and Schedule Generated
    ↓
Collections Tracking Begins
```

---

## Workflow 3 — Payment Collection to Financial Summary

```
Payment Due Date Arrives (from payment schedule)
    ↓
Collections Officer monitors overdue accounts
    ↓
Buyer makes payment — receipt recorded
    ↓
Receipt matched to schedule line
    ↓
If fully matched: line closed
    ↓
If unmatched after 7 days: alert raised
    ↓
If unmatched after 30 days: escalation alert raised
    ↓
Collected amounts feed into Finance Summary
    ↓
Revenue Recognition events triggered
```

---

## Workflow 4 — Contract to Registration (Phase 2)

```
Contract Under Contract status
    ↓
Registration case created
    ↓
Document checklist initiated
    ↓
Documents collected and verified
    ↓
Submission to registration authority
    ↓
Title deed received
    ↓
Unit status → Registered
    ↓
Title deed recorded
```

---

## Workflow 5 — Price Override Approval

```
Sales requests price override for a unit
    ↓
System checks override percentage
    ↓
If ≤2%: routed to Sales Manager for approval
If ≤5%: routed to Development Director for approval
If >5%: routed to CEO for approval
    ↓
Approver reviews and decides
    ↓
If approved: price updated on unit, audit log recorded
If rejected: unit retains original price
```

---

## Workflow 6 — Feasibility Approval

```
Feasibility Analyst creates scenario
    ↓
Revenue and cost assumptions defined
    ↓
Cashflow timing assumptions defined
    ↓
System calculates IRR, NPV, gross margin, break-even
    ↓
Analyst submits scenario for review
    ↓
Development Director / CEO reviews
    ↓
If approved: scenario locked, project proceeds to pricing
If rejected: analyst revises assumptions and resubmits
```
