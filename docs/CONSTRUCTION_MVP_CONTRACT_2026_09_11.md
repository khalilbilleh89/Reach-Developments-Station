# Construction MVP — Contract/commitment candidate

Base: merged Budget #287 (`327ed35`). Authority: the
[MVP finish plan](UX_MVP_FINISH_2026_09_11.md), shared
[Budget/Contract plan](CONSTRUCTION_MVP_BUDGET_2026_09_11.md), and
[Engineering Rules](ENGINEERING_RULES.md).

## Operator journey

Create a contract draft in the project's base currency, record vendor/terms,
allocate its exact value to cost-code lines, submit, then independently authorize
and activate against the active budget. Unlike Budget, Contract has no separate
approval status: the existing activation is the authorization decision. Finance
or Project Management prepares; a different Finance/CFO actor activates, retaining
the existing Master exception.

Draft terms and lines are editable. Submitted records stay frozen: cancel an
uncommitted record with a reason and prepare a corrected draft. No financial row
is deleted. A draft line can be explicitly zeroed or reassigned; cancellation
retains its lines. Complete/terminate operate on active contracts only and leave
the standing commitment unchanged. Financial reduction still requires the
existing governed variation process, whose UI is outside this PR.

The register exposes Create contract draft and retains search/status, selected
contract and file tab in URL state. Closing the file retains register filters.
Manage contract shows the header/line totals, permitted actions, server blockers,
line editing and lifecycle timestamps/reasons. The existing Position, Lines and
related-record tabs remain. Uncommitted values are labelled as proposals in the
register and file. Budget/cost-code navigation is available from the file.

Forms reuse FormDialog draft protection, exact monetary strings and existing
percentage conversion. Unstated tax remains null, distinct from explicit zero.
Failures retain values/reasons; refreshed eligibility disables a now-invalid
confirmation. A failed primary refresh disables writes while keeping the form
cancelable. Related-read failures do not hide the primary contract or masquerade
as complete empty registers; Retry/Refresh is explicit.

## API and governance changes

- Add `PUT /projects/{project_id}/construction/contracts/{contract_id}` for full
  draft terms using the existing strict creation fields. Project/row locks and
  preparer authorization apply; submitted/live/terminal records cannot be edited.
- Budget/commitment math is unchanged. Shared read-only submit, activate and close
  validators supply actor-specific workflow blockers and run again under write
  locks. Exact reconciliation, currency, independent checking and headroom rules
  remain existing service rules.
- Contract detail adds workflow eligibility, exact line total, currency identifier,
  lifecycle timestamps and termination/cancellation reasons.
- Draft header changes and line writes record attributable audit snapshots via
  `construction.contract_updated` and `construction.contract_line_written`.
- Non-blank reference/vendor and ordered planned dates receive readable 422
  validation instead of reaching the equivalent database constraints.

No new dependency, schema, migration, currency conversion, financial formula,
rounding rule, state framework or Construction C editor. API and frontend deploy
as a matched build. Rollback restores the prior application; existing records
and statuses remain compatible and the audit history remains retained.

## Validation and remaining acceptance

Final local/CI results are recorded in the Draft PR. PostgreSQL integration
coverage includes exact draft editing, role refusal, frozen submitted/live terms,
independent activation, budget refusal, cancellation history and commitment
preservation on completion. Component tests cover exact amounts/percentages,
null versus zero tax, zeroed lines, reason retention, failed-refresh safety and
changed eligibility during an open confirmation.

Live HTTP acceptance used a separate synthetic PostgreSQL clone:

| Scenario | Observed result |
| --- | --- |
| CT-UAT-01 | Finance edited terms to 180,000.25, reconciled a cost-code line and submitted; independent CFO activated and completed; commitment remained 180,000.25 |
| CT-UAT-02 | A 2,000,000 contract exceeded BLD-01 headroom; read eligibility matched the activation refusal; Finance cancelled it with reason, submission timestamp and line retained |

**Browser/mobile acceptance is pending.** Browser automation could not initialize
after the laptop shutdown (`failed to write kernel assets`, missing path), even
after resetting its session. This is not a browser pass. Before Ready, inspect
create/edit forms, dirty Cancel/Stay, failed-write retention, drawer/tab/history
return, independent activation, cancellation, and narrow-screen actions in the
actual UI. API/component tests do not substitute for those checks or real
operator UAT. The earlier Budget screenshots do not validate this candidate.

Independent review, exact-head Full Backend/Frontend and human merge remain
separate gates. Narrow UX-13 is next after Contract review and merge, followed
by operator UAT, broader Construction-scope reconciliation and the MVP freeze.
