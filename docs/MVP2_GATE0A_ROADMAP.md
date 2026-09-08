# MVP 2 Gate 0A roadmap — three PRs

Authority: [MVP2_GATE0A_PRODUCT_SPEC.md](MVP2_GATE0A_PRODUCT_SPEC.md).
Evidence: [MVP2_GATE0A_ACCEPTANCE.md](MVP2_GATE0A_ACCEPTANCE.md).

- **G0A-01 — MERGED:** Project Structure, Setup Simplification & Pre-Launch (#266/#267).
- **G0A-02 — MERGED:** Consultant Engineer & Commission Distribution (#268).
- **G0A-03 — FINAL PROMOTION:** Project Analysis Suite, Integrated Gate 0A Acceptance & Main Promotion.

While G0A-03 is Draft, Gate 0A is **2 / 3 merged** and independent acceptance is
pending. When the independently approved G0A-03 candidate is present on `main`,
Gate 0A is **3 / 3 complete** and the MVP 2 stakeholder iteration is complete.
This merge condition is the completion event; no fourth promotion PR is required.

MVP 1 foundation and MVP 2 Gate 0 are complete. **True MVP 3 — NOT STARTED**.

## History and closure

Owner closure #264 remains historical. Khalil subsequently clarified that Gate 0A
belongs to the same MVP 2 operator iteration. MVP 2 was reopened for that work.
Final G0A-03 promotion supersedes the old scope assumption without deleting or
retroactively passing historical Partial/Pending UAT evidence.

## Final branch and CI policy

`integration/mvp3` is historical technical debt, not a product version. G0A-01/02
used it for Smoke integration. G0A-03 starts at its latest head, merges latest
main without dropping G0A-02, and targets **main as Draft**. Main must be an
ancestor of the final candidate. Draft runs Backend Fast and Frontend.

Only after independent review explicitly authorizes Mark Ready may the configured
Backend Static / Structural, four Full Backend shards, Backend aggregator and
Frontend run. Smoke/Fast are not Full evidence. Do not edit the exact candidate
after Full green; a changed head invalidates that gate. The implementation agent
must not mark Ready or merge.

After human merge, verify main SHA and main CI, Render's main deploy, boot,
0017_consultant_commissions, Overview analysis and core navigation. Retire/delete
`integration/mvp3` only after successful main merge and post-merge verification;
do not delete it during implementation. True MVP 3 requires a new planning session
and does not inherit this branch or a new roadmap automatically.
