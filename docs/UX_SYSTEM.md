# Reach Experience 4.1 — UX System

Reach is a real-estate development operating system. Its interface must help a developer understand capital, assets, commitments and delivery before inspecting individual records. Experience 4 uses architectural graphite, a warm mineral canvas, strong financial typography and clearly separated working surfaces.

This document replaces the visual rules of Product Experience 3.0. Business truth, permissions and accessibility remain constraints on every composition. The design system is implemented in `frontend/src/app/globals.css` and the canonical exports in `frontend/src/components/ui/index.ts`.

Experience 4.1 refines three scales within that system: Portfolio exposes development attention and denomination-specific capital, Project identifies the development and its current position, and Unit 360 presents a physical asset with independently owned commercial, legal, collection and delivery states. Registers connect those scales without losing the source context.

## 1. Composition and hierarchy

Choose the information hierarchy before choosing containers:

1. Identify the development, asset or account and its location.
2. Lead with the server-reported figure or status that supports the decision.
3. Show exceptions and the action that opens the owning workflow.
4. Keep operational registers compact and scannable.
5. Place detailed basis, history and secondary evidence behind labelled disclosures or record sections.

A page is not a collection of equal KPI cards. Use open bands for counts, ink for an executive position, white for working records, and quiet inset surfaces for supporting evidence. A supporting section need not have a card. Avoid repeated descriptions, duplicate header facts, empty columns and decorative charts.

## 2. Tokens and theme

There is one explicit light theme. Ink navigation and executive positions are part of that theme; they do not change with the operating system. All literal colours belong to the one top-level `:root` block. Semantic aliases inside a component scope may refer to these tokens. Responsive token changes belong in the existing media queries.

| Role | Token | Value |
| --- | --- | --- |
| Mineral canvas | `--canvas` | `#f2f2ee` |
| Working surface | `--surface` | `#ffffff` |
| Supporting ground | `--surface-secondary` | `#f7f7f4` |
| Navigation | `--nav-bg` | `#14232e` |
| Executive ground | `--command-bg` | `#1b333e` |
| Executive text | `--command-text` | `#f4f8f7` |
| Executive secondary text | `--command-muted` | `#b1c8ce` |
| Primary text | `--text-primary` | `#17272e` |
| Secondary text | `--text-secondary` | `#526369` |
| Quiet text | `--text-muted` | `#5b6c70` |
| Accent | `--accent` | `#245cce` |
| Success / warning / danger | `--success`, `--warning`, `--danger` | Emerald, amber, restrained red |
| Controls / surfaces / tags | `--radius-control`, `--radius-card`, `--radius-tag` | 8px / 16px / 5px |
| Rail / context bar | `--sidebar-width`, `--context-bar-height` | 15.5rem / 4rem |
| Record width | `--drawer-width` | 70rem maximum |

The command surface remaps text, lines, actions and semantic foreground/background pairs together. A light foreground cannot be placed on a light status badge simply because its parent is dark. Check contrast in the actual containing surface.

Spacing uses the existing 4, 8, 12, 16, 24, 32, 48 and 64px scale. Controls, rows, forms and executive surfaces have different density. Borders separate data and define controls; they do not frame every paragraph. Small shadows separate white surfaces from the canvas; stronger elevation belongs to floating drawers and dialogs.

## 3. Typography

Use the installed system sans stack. Inter is used only where already installed; no web font is fetched. The mono stack identifies references, rather than styling all money as code. Financial figures use tabular numerals.

| Role | Token | Size |
| --- | --- | --- |
| Development identity | `--title-plate` | 2.75rem |
| Page / record title | `--title-page`, `--title-record` | 2.125rem |
| Card heading | `--title-section` | 1.125rem |
| Section heading | `--text-lg` | 1.0625rem |
| Main executive value | `--metric-hero-lg` | 3.25rem |
| Record / compact lead value | `--metric-hero` | 2.75rem |
| Supporting financial value | `--metric` | 1.625rem |
| Body / register | `--text-base`, `--text-sm` | 14px / 13px |

The page title remains prominent on a compact register page; `compact` reduces spacing, not the title's importance. Labels below numbers explain their basis. Long amounts must not overlap neighbouring figures or escape the viewport. Preserve the amount and currency; adapt layout before truncating information.

## 4. Shell and navigation

The graphite rail contains the architectural Reach mark, current-development identity, lifecycle groups, user context and settings. The project switcher is integrated into the rail. Active navigation has an accent marker and legible text, while the rest of the rail stays quiet.

Portfolio is a distinct destination above the current-development switcher. Its visibility and requests remain subject to the existing Portfolio roles; it is not another project department. Long context-bar breadcrumbs truncate within their own bounds.

The context bar carries breadcrumbs, project status and base currency. On phones, preserve the project breadcrumb instead of the Projects directory breadcrumb; long project names wrap. Record tabs scroll with the page below 768px so they cannot stick behind a taller project bar. The page header carries purpose, identity and actions. Below 768px, actions occupy a separate row beneath the full-width identity so titles never compete with controls for a narrow column. Avoid adding another competing navigation layer.

Sales gives the current sale or reservation the primary first-column link, with the buyer alongside it. View unit is secondary; available units without a current transaction expose Reserve in the same visible column. Record navigation retains both the same-project register origin and the immediate parent, including its tab. Back follows the parent, and an origin link returns directly to the register. Use the shared contextual URL builder for post-create redirects as well as links. See the [September follow-up roadmap](UX_ROADMAP_2026_09_10.md) for the bounded trail and acceptance evidence.

Keep the existing `auto`, `expanded` and `collapsed` rail preference and `reach.rail` persistence. Below 75rem the automatic rail collapses; below 64rem navigation opens as a modal drawer. The same catalogue supplies labels, route keys and visibility. `projectHref` and `settingsHref` remain the route builders. A project switch preserves the selected section where possible.

Visibility mirrors the backend's role sets. Gate requests before fetching; hiding a rendered field is not permission enforcement. Preserve all setup, password-change and project-access gates.

## 5. Canonical primitives

Import from `@/components/ui`. Extend the canonical component where it already owns a responsibility. Do not add `CardV4`, `NewDrawer`, aliases, duplicate component libraries or a second stylesheet layer.

| Primitive | Responsibility |
| --- | --- |
| `PageHeader` | One page identity, optional module glyph, subtitle, status, metadata and actions |
| `SectionHeader` | A labelled division; level 2 for a page section, level 3 inside it |
| `Card`, `SubPanel` | Working surfaces and supporting sections; `command`, `attention`, `subtle`, or ordinary weight |
| `Position`, `PositionFigure` | Exact reported figures with one lead; inline or split composition |
| `PositionSupport` | The supporting facts and basis of the position |
| `Metric`, `MetricGroup`, `StatStrip` | Smaller measurements and count bands |
| `Breakdown`, `Waterfall`, `Distribution`, `Meter` | Reported components or progress, with explicit labels |
| `CountComposition`, `CountSeries` | Server count composition and signed count observations, with exact text equivalents |
| `AttentionList` | Reported severity or count, reason, context, optional source evidence, and an action to the owning workflow |
| `DataToolbar`, `ToolbarFilter` | Search, filters, result count, reset and register actions |
| `TableScroll`, `IdentityCell`, `PlaceCell` | Accessible registers, asset identity and physical context |
| `Drawer` | A record opened over its source register, including identity, facts, actions and section tabs |
| `Tabs`, `TabPanel` | Workspace, record and analysis navigation with shared keyboard semantics |
| `Disclosure` | Native details/summary semantics, a consistent target and chevron, optional context and focus refs |
| `Field`, `FieldRow`, `FormSection` | Labelled fields and coherent groups with a dedicated field body |
| `MoneyInput`, `RateInput` | Exact string input with denomination or percentage affordance |
| `FormActions`, `StickyActions` | Save, cancel and busy state |
| `ConfirmDialog`, `PromptDialog`, `FormDialog` | Named modal decisions and focused editing |
| `Badge`, `StatusDot`, `Notice` | Explicit state and feedback; colour supplements words |
| `EmptyState`, `Loading` | Missing-data explanations and loading shapes |

Retired aliases `Panel`, `Stat`, `StatRow` and `FilterBar` remain retired. Experience 4 removes raw screen-owned disclosure markup and the former command-card gradient hairline. It replaces existing rules in place; it does not append an override theme.

## 6. Registers and filters

The identity column represents an asset or account, not a database key. Use a module glyph where it helps recognise the asset, a strong reference, then short metadata. Keep phase, building and floor context readable. Buyer names and explanatory fields can wrap; numeric table columns stay aligned and intact.

Use a quiet tinted header strip, row separators, a restrained hover state and a visible selected record. Keep the first column pinned when appropriate. A wide register scrolls inside `TableScroll`; the page does not scroll sideways. Every table has a caption and scoped headings.

Use `stickyHeader` for long operational registers: the bounded scroll region retains column headings while reading rows. `fixedFirst` retains identity on desktop and releases it at phone width so it does not cover the other columns. `DataToolbar.activeSummary` names applied search and selected context even while the filters are collapsed; the applied indicator and reset remain available.

Search and filters are individual, clearly labelled controls on the canvas. Below 60rem filters collapse behind a button with `aria-expanded` and `aria-controls`. Applied filters remain apparent through the applied indicator, result count and reset action. Render each filter once; collapsing must not clear its value or create duplicate controls. Show the primary register action beside the count.

Inventory keeps Phases, Buildings, Floors and Units as first-class views. Each shows its own objects, and drill-down preserves context. Keep contextual manual creation and the existing workbook import/review process.

## 7. Record files and forms

Desktop drawers float with a small inset, rounded corners and a warm body beneath a white identity header. The header prioritises the reference, physical location, current state and one important figure. Supporting facts must add information rather than repeat the whole body.

Land separates tenure and acquisition. Its area is the recorded physical measure; acquisition is explicitly a cost basis, not a valuation. Planning, utilities and documents remain separate sections. Unknown values remain unknown. Land classifications remain free text with optional suggestions; Settings vocabularies must not reject valid typed classifications.

Unit 360 keeps four independent status dimensions in its header through `UnitStanding`: commercial, legal, collection and delivery. The headline uses the returned active contract net price (ex tax) when readable. A committed unit with a withheld contract must not substitute asking price; a failed contract read explicitly reports unavailable. Uncontracted units may show the authorized asking price. Internal and gross areas retain their units. The overview leads with the physical profile and location, then collections, price and commitment; release readiness is supporting disclosed evidence. Physical record, pricing, sales/legal, collections, construction/delivery, release and history remain separate tabs. Property characteristics come only from recorded fields; parking and storage remain separate assets, excluded from gross area.

Workspace tabs use a contained rail, record tabs use a section underline, and Analysis tabs use a compact segmented treatment. All share roving focus, arrow keys, Home/End, stable ids and labelled panels. Revealing a selected tab scrolls only its own horizontal rail; mounting a tab group must never move the page.

On phones the record becomes full-screen and its whole content can scroll, so a tall header cannot trap the body in a clipped remainder. Closing returns focus to the source control. Desktop forms in a wide drawer can place the group description beside the fields; mobile forms stack.

Forms retain field labels, optional markers, validation, busy state, exact input strings and save/cancel behavior. Permit types are created through the project-scoped flow; a retired value remains readable but is not offered for a new selection. Do not add global vocabulary administration to a domain form.

## 8. Executive and operational workspaces

**Project Overview:** development identity, economic position and exception queue lead. Department detail is available through a labelled disclosure. Analysis follows with its own context and evidence; collections and management reports retain their owning-source data. Unavailable attention sources must be reported before claiming nothing is flagged.

**Portfolio:** development counts and the server's sales penetration establish the executive position. Prioritized risks use the same `AttentionList` as Project, retaining the server's severity, category, reason, project identity, source value/currency, observation date and source basis. Open-source actions lead to the existing owner; attention rows do not dismiss, score or resolve risks. Capital bands select original `money` records by currency and metric code without summing them. Contracted value, confirmed receipts, unrestricted cash and construction EAC are labelled separately; the complete monetary register, contributing/missing coverage and risk-evaluation coverage remain available. Prose source values wrap; decimal amounts retain their exact digits.

**Project Analysis:** observation period and snapshot context precede reported findings. Inventory absorption and the run-rate estimate occupy distinct surfaces. Display partial/unavailable coverage and sample size explicitly. Detailed source explanations and secondary tables are disclosed on demand. Financial analysis leads with one selected month's reported cash movement, showing every returned currency separately; the full monthly register and refund/financing detail remain disclosed evidence. Selecting an existing month must never aggregate, convert or calculate amounts. Contracted demand remains distinct from actual cash. Technical product mix and recorded feature coverage occupy distinct surfaces, retaining their populations, denominators and availability. Never fabricate a management score, trend or comparison.

**Sales and payment plans:** lead with contracted value or the agreed schedule, then the register and the owning deal/plan file. A scheduled instalment is not a receipt. Preserve approval gates, legal status, cancellation behavior, trigger controls and reconciliation.

**Collections and commissions:** overdue, outstanding, collected and unapplied amounts remain separately labelled. Ageing uses the selected date. Commission grant, rate, base, beneficiary distribution and release checks retain their original meanings. Never infer a financial total from visible rows.

**Construction:** completion variance leads the cost-control view; budget, revised commitment and certified work remain labelled. Cost control excludes tax. Payable includes tax and has a separate surface. Forecast-cutoff certified work must not be presented as today's certified figure. Preserve dispute, retention, variation and approval semantics.

**Cashflow:** unrestricted cash leads, with total and restricted cash alongside. Basis and forecast status remain visible. Funding windows, lowest cash position, peak requirement, NPV and equity IRR use the server's values and availability. A missing or stale forecast must remain apparent.

**Supporting workspaces:** permits, consultant design, pre-launch expenses, documents and access use the same headers, surfaces, registers, forms and dialogs. Account settings separate security context from the password form. Users and audit remain operational registers; scope and authority are unchanged.

## 9. Financial and business boundaries

- Money crosses the API as decimal strings. `money()` groups the existing digits and displays the resolved currency; it does not round, convert or aggregate them.
- Resolve each record's denomination. Never guess a currency or combine different currencies.
- Use the string-based rate formatters and business-date formatting. A date-only value is a calendar date, not a timezone conversion.
- No browser sums, ratios, margins, forecasts, economics, derived progress or invented financial series. Existing count-only behavior stays separate from money.
- `Meter` displays a percentage already reported by the server. Never invent a completion percentage for visual effect.
- Portfolio uses the neutral `Meter` with `sales_penetration.percentage`; numerator, denominator and availability remain visible. Neutral styling does not imply a risk threshold.
- `CountComposition` consumes `analysis/fundamental.position.commercial` and labels the full `position.total_units` population and `context.snapshot_as_of`. CSS distributes the returned non-negative counts; no displayed ratio or total is calculated. Legal and delivery counts remain separate dimensions.
- `CountSeries` consumes `analysis/fundamental.monthly_sales[].net_absorption` and `month`, with `context.period_from`, `period_to` and `sales_basis` coverage. SVG arithmetic determines coordinates of integer counts only. Preserve negative observations, zero, exact printed counts, period labels and accessible units. Keep the source monthly table and suppress the plot for unavailable or absent observations.
- Financial series, a cashflow curve or collections composition require an owning API's comparable source series and safe normalized geometry/basis before new plots can be introduced. Current money remains in exact labelled figures and source tables. Do not normalize financial decimal strings in the browser, combine financial with physical construction progress, or invent a collection ratio.
- Preserve API payloads, backend formulas, schema, authentication, role checks and approval workflows.
- Distinguish loading, absent, denied, failed, partial and zero. Keep a failure visible; never replace it with a comforting zero or a false empty state.

## 10. Accessibility and responsive acceptance

Validate at 1600, 1440, 1280, 1024, 768 and 390 pixels, with real loaded local fixtures. Check desktop operations and phone navigation separately.

- One page `h1`, named sections, labelled forms and buttons.
- Native disclosure keyboard behavior and visibly distinct expanded state.
- Tabs move selection and focus together, with no page jump.
- Shared overlay handling for drawers, navigation, switcher and dialogs: initial focus, containment, Escape on the topmost layer, background isolation and focus restoration.
- Tables remain keyboard-scrollable; fixed identities do not cover adjacent data.
- Mobile filters stay operable and applied state stays visible.
- Nested dialogs remain usable over a record. Long forms and long amounts do not clip.
- Focus indicators work on both light and ink surfaces. State is never conveyed by colour alone.
- Reduced motion suppresses entrance and transition effects. No animated counters or fabricated charts.

The source guards in `tests/test_product_experience.py` enforce architecture, permission and financial boundaries. They do not substitute for visual or keyboard review. Final evidence must use loaded data, settled layout and the production export, with comparable before/after crops.

## 11. Implementation and review

**M3-02 management surfaces:** Portfolio adds Outlook, Exceptions and Actions.
Outlook starts with the server-selected horizon and cash/funding source, then
offers contractual dues, commercial run-rate, EAC, permit/design dates and
management commitments in that order. Use a dense source register and one
focused source drawer; do not repeat executive cards for every project.
Forecast, scheduled contractual due and actual cash remain distinct labels.
Incomplete and undated coverage stays visible below the register.

Actions use server filters, including My Actions, and a versioned record drawer
with Action, Source and chronological History sections. Source risk severity
and action lateness are separate sections in Exceptions. Project Overview has
compact open/overdue/next-due counts and a filtered register link. Management
writers may create a project action there. Read-only roles show no mutation
controls and never request assignment candidates. Current owner names and
attributed event times are readable; business dates never undergo timezone
conversion. Source resolution and action completion remain independent.

The frontend remains a Next.js static export served by FastAPI from `frontend/out`. Keep the current dependencies and route architecture. Add no UI framework, chart package, font request or state-management layer for presentation work.

Run lint, TypeScript, the production build, Product Experience guards and the relevant frontend contract checks. Review the console, responsive results and interaction evidence. When integration advances during a horizontal redesign, synchronize carefully and visually integrate new screens without changing their business implementation. Describe material limitations and remaining visual debt in the handoff.

## Form safety and request outcomes

Use `DraftBoundary` for state-owned inline editors, comparing against the saved
record and resetting only after persistence or confirmed discard. Shared form
and reason dialogs guard their own inputs; Drawer asks contained drafts before
closing. Mark inline close/version-change controls with `data-leaves-editor`.
Use `requestFormLeave` for non-link project selection that replaces an editor.
Keep inputs in memory; never persist customer or transaction drafts in storage.

Reason dialogs remain mounted after failed mutations. Close on successful
persistence before refreshing the record, so refresh failure cannot invite a
second mutation. Distinguish a conflict from a failed read and offer explicit
refresh without clearing the reason. Prevent navigation/editing while saving.

Readers must distinguish loading, failed, denied and empty. `useAnswer` pairs
results with request identity and exposes Retry. Never label amounts from the
previous date/filter as current data. Retain structured `ApiError.fieldErrors`
where an editor can identify the affected fields or instalment rows; use the
shared validation summary and named controls for focus/error association.
