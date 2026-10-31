# Reach Design System — Experience 6 component catalogue

This folder records the component styles the owner approved on 31 Oct 2026 after
a four-page interactive review. It is the single source every build takes from:
when a screen needs a chart, a bar, a table, a form, a record page or a shell,
it is built the way the matching entry here says, and no other way.

`docs/UX_SYSTEM.md` remains the design authority for composition, tokens,
typography and the financial boundary; its §12 points here. This catalogue adds
the component-level decisions. Where the two disagree, this catalogue is newer.

## How to use it

1. Find the component in the table below and read its reference page in
   `references/`. Each page is a self-contained HTML file with live, clickable
   examples drawn with Pyla Pearl's own figures. Open it in a browser.
2. Build the canonical primitive in `frontend/src/components/ui/` so that it
   renders the approved option. Do not copy the reference page's CSS; it is a
   mock-up, not production code. Production styles live in `globals.css` and
   read the tokens in `docs/UX_SYSTEM.md` §2.
3. Options listed as "rejected" or "not picked" are not to be built.

## Approved components

| Code | Component | Approved | Reference | Status |
| --- | --- | --- | --- | --- |
| A | Column chart | A1 quiet columns (hover values, no zero labels, latest active month in gold); A2 KPI + spark bars (number leads, trend strip beside it); A3 cumulative area | `references/01-…` | built (PR 2, #415) |
| B | Stacked bar (distribution) | B1 slim 8px bar with count + share in the legend; B3 unit grid (one square per unit); B4 one row per status; B5 ring. B2 labelled segments: optional | `references/01-…` | built (PR 2, #415) |
| C | Data note (source & method) | C1 info icon beside the section title opening a popover; C2 sample-size chip in the header; C4 data-quality meter for partial coverage. The standalone "Available · n records · Method" line is retired | `references/01-…` | built (PR 2, #415) |
| D | Collapsed rows | D1 segmented toggle + always-visible table; D2 underline tabs; D4 summary tiles with a headline answer. Accordions are kept only for secondary evidence, with the chevron on the left (D3 style) | `references/01-…` | built (PR 3, #416) |
| E | Tables (registers) | E1 sortable, selectable register with sticky header, bulk action bar and row menu; E3 inline editing (double-click, Enter/Escape); E4 compact/comfortable density toggle, remembered per person; E5 card rows for records with few columns. E2 expandable rows: not picked | `references/02-…` | built (PR 4, #417) |
| F | Finding things | F1 side drawer to peek at a record without leaving the list; F2 command palette (⌘K) searching projects, units, buyers, screens and actions; F3 filter chips + saved views (server-stored per user); F4 date-range presets with custom | `references/02-…` | F2, F3, F4 built (PR 4 #417, PR 5 #418); F1 not built, see Deviations |
| G | Feedback | G1 toasts with Undo for destructive actions; G2 sticky banner for must-act conditions; G3 skeleton loading. G4 empty states: owner undecided, keep current `EmptyState` | `references/02-…` | G1, G2 built (PR 1, #414); G3 skeletons already in use; G4 unchanged |
| H | Stat tiles & progress | H1 equal tiles with label above, number below, change and trend line; H3c progress parts: stepper with the current step on a gold panel, segmented stage bar with the current segment gold, rings with the one in focus on gold. H2 (lead + ledger tile): rejected | `references/02-…`, `references/04-…` | built (PR 8, #421) |
| I | Small parts | I1 one status-pill style with a leading dot (colour only for meaning); I2 tooltips, switches, avatar stacks, keyboard hints | `references/02-…` | built (PR 1, #414) |
| J | Forms | J1 modern fields (focus ring, hint and error under the field, money field with fixed currency and right-aligned digits); J2 choice cards and segmented toggles instead of short dropdowns; J3 sectioned long form with section links and a sticky save bar showing unsaved state; J4 stepped flow for multi-step actions (new reservation, record payment, SPA) | `references/03-…` | built (PR 1 #414, PR 6 #419) |
| K | Record pages | K4 workspace: head with status and two actions, money strip with the lead figure on gold, a "what's next" bar, facts beside activity, section tabs. K5 two-pane and K6 journey-led remain available for specific records. K1 and K3: rejected | `references/04-…` | K4 built (PR 7, #420) |
| L | Navigation | L1 graphite rail with tighter groups, counts, project switcher card, collapsible to icons; top bar with breadcrumb, global search and avatar. L3 phone bottom tab bar for the five most used areas. L2 section tabs: not picked | `references/03-…` | L1, L3 built (PR 5, #418); rail counts see Deviations |
| M | Sign-in | M1 split: graphite brand panel with the logo and a line about the company, form beside it; centred card below 720px | `references/03-…` | built (PR 9, #422) |

## Shared rules the owner set

- Every component is interactive: hover values, click to open, keyboard reachable.
- The row menu ("⋯") holds a row's secondary actions on every table; a row with a single action keeps it visible.
- Colour on a figure is reserved for danger; the current step, segment or focus is shown on gold, never as a gold number.
- A missing figure is a statement in muted text, never a hero.
- On a phone, tables stack into labelled cards; charts fit the width or lead with the number.

## Delivery plan

| PR | Scope |
| --- | --- |
| 0 | This catalogue, the reference pages and `docs/UX_SYSTEM.md` §12 |
| 1 | Foundations: status pills (I1), tooltips/switches/avatars/kbd (I2), modern fields and money field (J1), toasts/banners/skeletons (G1–G3), gold state tokens |
| 2 | Charts, bars and data notes (A, B, C) across the 1 chart, 4 bars and 13 notes in use |
| 3 | Accordions replaced by toggles, tabs and summary tiles (D) across the 52 in use |
| 4 | Registers: E1 E3 E4 E5, filter chips and saved views (F3, server-stored), date presets (F4) |
| 5 | Shell: rail and top bar (L1), command palette with a search endpoint (F2), side drawer (F1), phone bottom tabs (L3) |
| 6 | Forms and flows: J2, J3, J4 |
| 7 | Record pages: K4 on units, sales, buyers, collection accounts, permits and contracts |
| 8 | Stat tiles and progress: H1, H3c |
| 9 | Sign-in: M1 |
| 10 | Audit: every screen against this catalogue; leftover mismatches fixed |

Each PR opens ready for review once local checks pass; a human merges.

## Deviations recorded during delivery

What the catalogue asked for and the delivery did not build, with the reason. Each is a decision for the owner, not an omission.

- **F1 side drawer** — not built. `AGENTS.md` and `docs/ENGINEERING_RULES.md` prohibit side drawers at every viewport; a catalogue entry does not override an engineering rule. If F1 is wanted, the rule changes first in its own PR.
- **A2 computed lead figure** — the chart component accepts a lead figure, but the Overview does not pass one: the server publishes no period total for net sales, and the browser does not add one up.
- **B1 share percentages** — the slim bar's legend prints each count only; the share it used to print was computed in the browser from a sum the server does not supply.
- **H1 change figures and trend lines** — tiles carry the figure and its note; the server publishes no prior-period value for them.
- **L1 counts on the rail** — the only per-module counts the server publishes are the Overview's attention items, assembled per screen; a rail count needs its own endpoint.
- **K4 facts beside activity** — the strip and next line are built on all six records; the activity panel needs a per-record event feed and was left out rather than drawn from partial data.
- **J4 SPA preparation flow** — the SPA details form holds two fields, which do not make a stepped flow; reservations and receipts are stepped.
- **M1 panel figures** — the sign-in panel carries no counts: a visitor who has not signed in has no session for any endpoint to answer.
- **Register sorting** — client-side sorting is offered only where the screen holds every row (Collections); server-paginated registers (Inventory, Sales) keep the server's order so a sorted page never implies a sorted set.
