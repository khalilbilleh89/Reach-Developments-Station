# True MVP3 roadmap

MVP1 and MVP2 are complete. Historical migration/go-live and UAT evidence remains
unchanged. UX-04 is the merged horizontal prerequisite, not a fourth MVP3 PR.

1. **M3-01 — Portfolio Command Center & Deterministic Risk Monitoring:** merged in PR #273 (`5363388`).
2. **M3-02 — Forward Outlook, Exceptions & Management Actions:** merged in PR #275 (`fceb047`).
3. **M3-03 — Historical Intelligence, Board Reporting & Final MVP3 Acceptance:** merged in PR #279 (`1d0edfe`).

Merged milestones: **3 / 3**. This does not claim deployment or alter historical UAT.

Remaining product finish work is tracked in [the current finish plan](UX_MVP_FINISH_2026_09_11.md). Merge status does not establish operator UAT or production acceptance.

## Historical M3-03 candidate routing (superseded)

M3-03 branched from main `2e697c8` on `mvp3/m3-03-historical-board-reporting`.
PR #279 merged on 2026-09-10. The following candidate gates are historical.
Acceptance, exact-head Full CI, human merge, post-merge main verification,
migration deployment and production smoke remain separate gates.

## Historical M3-02 candidate routing (superseded)

M3-02 branches directly from main at `73036d8af8d98dfdc6be81034eae4ddbaeb233db`,
including Experience 4.1 / UX-06 (PR #274), and now includes main `96db2f9`
(UX-07 and Master Administrator, PRs #276/#277). Branch `mvp3/m3-02-forward-actions`
targets **main**. It was opened Draft and subsequently marked Ready externally;
the applicable exact-head gates are now Full CI and Frontend. Independent review
precedes merge and deployment. M3-03 does
not start here. The earlier integration routing below is historical.

## Historical M3-01 release routing (superseded)

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
