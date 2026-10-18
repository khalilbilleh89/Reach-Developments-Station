# Matrix studio

Creative / Matrix is a project strategy workspace with six templates: SWOT, PESTEL, Porter's Five Forces, BCG, Ansoff and Fishbone. Choose a template, enter a dated title and context/sources, add ideas or products, view the diagram, then save. Open saved cards to view, edit or delete analyses. Draft input is held in memory and protected on navigation; server failures retain it.

## Meaning and display

SWOT separates internal strengths/weaknesses and external opportunities/threats. PESTEL covers six environmental categories. Porter connects four external pressures to competitive rivalry. Ansoff uses existing/new products across columns and existing/new markets down rows. Fishbone connects six cause categories to a stated problem; causes remain user hypotheses unless evidenced in notes.

BCG requires exact Decimal market growth percentages and relative market-share multiples (own share divided by the largest competitor's share). A user-chosen positive growth threshold defaults to 10%; the share boundary is 1x. Equality belongs to high growth/share. Server classification returns Stars, Question marks, Cash cows or Dogs. Equal-size numbered markers are positioned using bounded piecewise axes around the two crossings, explicitly labelled as non-linear. Exact values and category remain in the legend, including negative growth and zero share. No revenue weighting, financial advice or automated business facts are implied. Preview uses the server and creates no persistent record.

## Security and persistence

All reads, previews and writes require whole-project scope; project managers and effective administrators may write, other whole-project members may read. A project row lock serializes writes. Full PUT requires a current version; stale updates/deletions return 409. Cross-project IDs return 404. Inputs are plain text, bounded to 100 items per analysis, and validated by framework. No attachments, rich text, external fetches or executable expressions are accepted.

Migration 0045_project_matrices follows 0044_team_job_description and adds only project_matrices. Payloads hold validated versioned analysis inputs, not transaction data. Create, edit and delete are audited. Delete retains the payload and attributed reason; embedded item deletion is recorded in the parent's save audit. No analysis references or mutates financial, sales or legal transactions. Downgrade refuses any retained rows, including deleted ones; roll forward or export/approve data handling first. Empty-schema downgrade is supported.

## Validation

Lifecycle/permissions/migration tests: tests/modules/test_project_matrix.py. UI interaction tests: frontend/tests/matrix.test.mjs. Validation results and unresolved checks are recorded in the PR; implementation is not proof of deployment.
