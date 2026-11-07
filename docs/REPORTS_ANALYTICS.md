# Reports / Analytics

Owner-requested project reporting surface under a new Reports category. Governed
by ENGINEERING_RULES.md. No schema, dependencies, writes or persistent report records.

## Contract and scope

GET /api/v1/projects/{project_id}/analysis/report composes current system evidence.
Financial Analysis readers plus whole-project membership are required. Phase-only
members and nonfinancial roles are refused before the report queries execute.
Navigation mirrors these roles. No buyer names, contact details or identity documents
are exported. Agent names are the recorded sale attribution.

Optional period_from / period_to (existing Analysis maximum 732 days), currency
(registered three-letter code), threshold (nonnegative, at most 12 integer and two
fractional digits). Default period uses existing Analysis's trailing 12-month window;
threshold defaults to 400000 in project currency, a user-adjustable analytical choice,
not a legal or residency assertion. Positions remain current even for old activity periods.

## Financial and count meanings

- Active primary inventory excludes inactive units. Attached sub-assets are separate
  tables. Sold KPI counts distinct active units with activated, standing contracts.
  Unsigned buyer registration and reservations are not activated sales.
- Threshold is strict greater-than net_contract_price_ex_tax; equality is separate.
  Standing period sales in other currencies are excluded and their count disclosed.
- Price achievement compares frozen reference price against frozen net contract price.
- Trends use existing Analysis activation and cancellation dates. Gross activations
  can include subsequently cancelled sales; net absorption subtracts cancellations.
- Agent and agent-branch charts use frozen agent_name / agent_branch on sales. Advisor
  is a separate chart using the existing Analysis user attribution. Nine leading
  groups plus a disclosed other bucket bound large categorical charts.
- Buyer portfolio counts distinct client records with standing purchases, not legal
  parties. KYC covers all current active buyer records, not just purchasers.
- Cash series uses Cashflow's confirmed standing actual source records, original
  currencies and business dates. No FX or cost-to-cash inference. Gross receipts
  include tax; net movement is not a bank balance.
- Collections position reuses Collections batch calculations. Unapplied receipts,
  overdue and refund liabilities overlap: they must not be summed. Unavailable
  overdue due to missing schedules or incompatible allocations remains null.
- Construction budget / revised commitments / EAC reuse Construction batch reads,
  excluding tax. Missing or other-currency sources remain null, never zero.
- Permit and construction stage counts use existing Technical Analysis sources.
  Stage counts overlap and are not an overall certified completion percentage.

Decimal arithmetic is server-only. Chart percentages represent geometry, not new
business metrics. The browser formats original decimal strings without money rounding.
Each chart carries a short interpretation, source and applicable coverage note.

## Export and interaction

Activity dates, currency and price threshold apply on explicit Apply filters. Category
buttons narrow the screen; PDF always contains the full report. Refresh re-reads
sources. Loading, failed and denied reads cannot export stale report data.

Export PDF report invokes browser Print / Save as PDF. The dedicated A4 document
contains a cover summary and one chart per page, original exact monthly values,
source / explanation, page numbers and project/filter/generated-time headers.
It uses the same successful response as the screen: no second fetch or recalculation.
SVG charts remain vector; print colour adjustment preserves the brand palette.
No automatic email, server-side PDF storage or historical snapshot is implied.
Users retain and distribute their downloaded file. Source deletion/retention remains
owned by the existing modules; this GET-only report creates no deletable business record.

## Verification

Tests in tests/modules/test_project_analysis_report.py cover no-write reads, empty
and unavailable sources, exact threshold boundaries, cancellations, attribution,
invalid filters, unauthorized roles, phase restrictions and chart rollups. Existing
Analysis reconciliation tests cover the reused cash and sales calculations.
Frontend analyticsReport.test.mjs verifies exact money formatting, unavailable
values, printable exact values and empty charts. See PR for actual executed results.
