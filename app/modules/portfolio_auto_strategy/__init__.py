"""
portfolio_auto_strategy

Portfolio Auto-Strategy & Intervention Prioritization Engine (PR-V7-06).

Converts project-level strategy outputs (PR-V7-05) into a portfolio-wide
intervention priority ranking so management can answer:

  - Which projects need intervention now?
  - Which projects can be monitored passively?
  - Which projects have the highest expected upside?
  - Which projects are high-risk despite having a recommended strategy?
  - What are the top 5 portfolio actions?

All recommendations are read-only — no strategy decisions are persisted
and no source records are mutated.

Endpoints:
  GET /api/v1/portfolio/auto-strategy
    — Portfolio-level intervention prioritization and action summary.
"""
