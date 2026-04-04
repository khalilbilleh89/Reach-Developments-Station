"""
strategy_approval

Strategy Review & Approval Workflow (PR-V7-08).

Provides a governance layer above Portfolio Intelligence that formalises
strategy decision-making before execution.  Approval records are
immutable once created; only the status transitions are allowed.

Public API
----------
  POST /api/v1/projects/{id}/strategy-approval
  POST /api/v1/approvals/{id}/approve
  POST /api/v1/approvals/{id}/reject
  GET  /api/v1/projects/{id}/strategy-approval

State machine
-------------
  pending → approved
  pending → rejected

Forbidden
---------
  Reverse transitions (approved → pending, rejected → pending)
  Mutation of project, strategy, or execution-package records
  Execution of strategies
"""
