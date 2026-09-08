# MVP 2 Gate 0A roadmap — three PRs

Authority: [MVP2_GATE0A_PRODUCT_SPEC.md](MVP2_GATE0A_PRODUCT_SPEC.md). Acceptance:
[MVP2_GATE0A_ACCEPTANCE.md](MVP2_GATE0A_ACCEPTANCE.md).

With G0A-01 integrated, Gate 0A is **1 / 3 merged**:

- **G0A-01 — MERGED:** Project Structure, Setup Simplification & Pre-Launch
- **G0A-02 — CURRENT / DRAFT REVIEW:** Consultant Engineer & Commission Distribution
- **G0A-03 — FINAL:** Project Analysis Suite, Integrated Acceptance & Hardening

The original five product PRs were compressed because the current implementation
agent can carry broader coherent scopes and accelerated Smoke/integration CI avoids
repeatedly paying for the full backend suite. Compression does not reduce financial
controls, security, database integrity, concurrency testing, exact-head independent
review, or final integrated full-suite acceptance.

## Product history

| Milestone | Status |
| --- | --- |
| MVP 1 | COMPLETE foundation |
| MVP 2 core Gate 0 delivery | COMPLETE |
| Previous owner closure | RECORDED HISTORICAL DECISION (#264) |
| Subsequent stakeholder clarification | Gate 0A belongs to the same MVP 2 iteration and remains outstanding |
| Current MVP 2 status | REOPENED FOR GATE 0A COMPLETION |
| True MVP 3 | NOT STARTED |

Historical Pending/Partial UAT evidence remains unchanged. This is a scope
reclassification, not a retroactive pass.

## Temporary integration workflow

`integration/mvp3` is a temporary technical branch retained because PR #265 already
configured accelerated CI around that name. It is historical technical debt and does
not define the product version.

Each Gate 0A implementation PR targets that branch as Draft and runs Backend Smoke +
Frontend. It is not marked Ready or merged by its implementation agent. Exact-head
independent review is required. A genuine full-risk exception must be declared rather
than silently weakening Smoke. G0A-03 performs final integrated full-suite acceptance
before promotion to `main`; after promotion, retire `integration/mvp3`.

G0A-02 does not claim Gate 0A complete. During Draft review the tracker is:

- G0A-01 — MERGED
- G0A-02 — CURRENT / DRAFT REVIEW
- G0A-03 — NOT STARTED
- Gate 0A — 1 / 3 MERGED
- True MVP 3 — NOT STARTED
