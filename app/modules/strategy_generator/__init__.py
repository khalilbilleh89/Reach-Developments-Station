"""
strategy_generator

Automated Strategy Generator — Decision Synthesis Layer (PR-V7-05).

Converts fragmented intelligence from absorption, pricing, phasing, and
simulation engines into a single recommended strategy per project, and
an aggregated portfolio strategy view.

No source records are mutated.  No strategy decisions are persisted.

Endpoints:
  GET /api/v1/projects/{project_id}/recommended-strategy
    — Generate and rank candidate strategies; return best strategy + top 3.
  GET /api/v1/portfolio/strategy-insights
    — Portfolio-wide strategy intelligence aggregated across all projects.
"""
