# True MVP3 roadmap

MVP1 and MVP2 are complete. Historical migration/go-live and UAT evidence remains
unchanged. UX-04 is the merged horizontal prerequisite, not a fourth MVP3 PR.

1. **M3-01 — Portfolio Command Center & Deterministic Risk Monitoring:** in progress.
2. **M3-02 — Forward Outlook, Exceptions & Management Actions:** not started.
3. **M3-03 — Historical Intelligence, Board Reporting & Final MVP3 Acceptance:** not started.

Production milestones: **0 / 3**. No completion is claimed before review and promotion.

M3-01 branches from integration/mvp3-management at
`be7cf9acc72a0d5ff0b0331111140a81bb2b8cab`. Latest main at release,
`8402d2371c7433017f31e574c04879b1374f553d`, is included through merge
`89dfc8400778ee56877be2c2c97d027df85c5465`; those base trees were identical.
The implementation branch is `mvp3/m3-01-portfolio-command-center`.

M3-01 and M3-02 target integration/mvp3-management as Draft and require Backend
Smoke and Frontend. Preserve the existing narrow reviewed CI routing; no new
exception or integration wildcard. Unknown/shared-risk selection remains fail-closed.
M3-03 promotes accumulated work to main, with Structural, complete Full shards,
Backend aggregator and Frontend. An implementation agent never merges or marks
Ready; independent review and the authorized human flow follow the draft handoff.

Authority: [product specification](MVP3_PRODUCT_SPEC.md).
Evidence: [acceptance](MVP3_ACCEPTANCE.md).
