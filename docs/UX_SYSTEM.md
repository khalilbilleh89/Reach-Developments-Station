# Product Experience 3.0 — Reach Developments Station

The product's design system, third edition. One light working surface, one
deep navigation rail, one token layer, one set of hand-written primitives, and
no framework: no component library, no icon package, no CSS framework, no
chart library, no client state library.

The first edition (PR-UX-01) made the product consistent. The second
(PR-UX-02, PR-UX-03) made it a workspace. This edition (PR-V2-00, the first
pull request of MVP 2) makes it a premium operating environment: the same
governance-grade engine underneath, presented the way the strongest modern
enterprise and fintech products present theirs. It is not a colour change. It
is a deliberate upgrade to hierarchy, density, typography, spatial rhythm,
record presentation, forms, registers, states and action placement — and it
made the system simpler, not larger.

The principle in one line:

> **Serious backend. Simple operating experience. Premium product presentation.**

Everything here lives in a few places:

| What                          | Where                                                         |
| ----------------------------- | ------------------------------------------------------------- |
| Tokens and every class        | `frontend/src/app/globals.css`                                |
| Primitives                    | `frontend/src/components/ui/`                                 |
| Shell, rail, switcher, crumbs | `frontend/src/components/shell/`                              |
| Role sets the shell mirrors   | `frontend/src/lib/roles.ts`                                   |
| One request, five answers     | `frontend/src/lib/answer.ts`                                  |
| Presentation of figures       | `frontend/src/lib/format.ts`, `frontend/src/lib/currency.tsx` |
| Project command centre        | `frontend/src/components/dashboard/`                          |
| The system's structural guard | `tests/test_product_experience.py`                            |

If a screen needs something this document does not describe, the answer is
almost always a new composition of what is here — not a new primitive, and
never a new dependency.

---

## 1. What this product is, and what that means for its interface

This is the record of what a real estate developer owns, what it is selling,
what it has agreed, what it is owed, and what it is spending to build. People
use it to answer questions they will later have to defend: to a board, to a
lender, to a buyer's lawyer, to an auditor.

Four consequences run through every decision below, and PR-V2-00 changed none
of them.

**Nothing on screen may be invented.** Every figure, status, blocker, gate and
total is a value the API returned on that request. The browser lays out and
labels; it never calculates a price, a discount, a tax, a margin, a total, an
allocation, a release eligibility, a funding gap or an approval requirement.
There is exactly one implementation of each of those, and it is on the server.

**Empty space beats a plausible number.** No placeholder cards, no sample
series, no charts drawn from nothing, no health scores, no trends, no "0%"
standing in for "not measured". Where a total cannot honestly be produced — a
project whose contracts are in two currencies — the screen says so and shows
nothing.

**What a role may not read, the browser does not ask for.** Navigation,
sections, record tabs and record headlines mirror the backend's permission
sets. Hiding a figure after fetching it is not restriction; it is a leak
waiting for a refactor. The rule is *do not ask*, never *fetch then hide*.

**A word carries the meaning; colour only repeats it.** Nothing on any screen
is understood by hue alone.

---

## 2. The operating experience

The previous editions frequently presented a page as: box, heading, small
explanation, another box, table, another form. Product Experience 3.0
organises every major page around one sequence:

```
CONTEXT   →   ANSWER   →   ACTION   →   DETAIL
```

Every major page makes three things obvious without parsing ten cards:

1. **Where am I?** — the rail, the context bar and the page header.
2. **What is the current position?** — one command surface, set large.
3. **What can or should I do next?** — one primary action, visibly primary.

Ask on every page: *what decision or action is this person here to make?*
Then make that answer visually dominant, and let everything else recede.

**Modern does not mean more decoration. Modern means better hierarchy.** The
system avoids excessive borders, card-within-card, grey boxes everywhere,
tiny text everywhere, pill badges sprayed across a screen, dead empty areas,
arbitrary shadows, decorative gradients, glassmorphism and dashboard
furniture. It reaches for whitespace, typography, hairlines, ruled bands,
grouped statements and structured rows instead.

### The anti-card rule

A card is a meaningful surface, not a border. A page does not get an
individual card for every number, status, heading, field group or tiny
subsection. Two things that belong together are composed together — as a
ruled band, a position with its support line, a statement with its total —
and a card is used only where a surface genuinely changes: the answer the
page exists to give, a register, an attention list, a form that opened.

The stylesheet enforces the spirit of this: there is one container primitive
(`Card`), one ruled band inside it (`SubPanel`), and the guard test fails if a
second copy of either appears anywhere.

---

## 3. Theme

**A light workspace and a deep rail.** `html { color-scheme: light; }`, and
there is no `prefers-color-scheme` rule and no `data-theme` hook anywhere in
the stylesheet — the guard test checks both.

The working surface is light because it gets printed, screenshotted into
board packs and shared as evidence, and a document that looks different on the
reviewer's machine than on the preparer's is a document somebody has to
explain. The rail is a deep charcoal-navy because it is chrome, not content:
it frames the work without competing with it.

A dark theme is a real piece of work — every token, every status colour,
every contrast pair — and half of one is worse than none. If one is ever
added, it is added at the token layer, deliberately, with every pair checked.

---

## 4. Tokens

All tokens are CSS custom properties, declared **once**, on a single `:root`.
Components never hard-code a colour, a radius, a spacing step, a size or a
duration; the guard fails the build on a literal hex colour outside the token
block, on an inline visual style in a component, and on a token block split
in two.

### Canvas and surfaces

| Token                 | Value     | Use                                                  |
| --------------------- | --------- | ---------------------------------------------------- |
| `--canvas`            | `#f5f6f8` | The cool neutral page behind everything.              |
| `--surface`           | `#ffffff` | Cards, the context bar, drawers, dialogs, registers.  |
| `--surface-secondary` | `#f8f9fb` | Affixes, notices, the empty-state icon well.          |
| `--surface-hover`     | `#f2f4f7` | Row and control hover.                                |
| `--surface-selected`  | `#edf2ff` | The selected row, option or segment.                  |
| `--surface-command`   | `#fbfcfe` | The command surface and the record facts strip.       |

The canvas moved from a warm administrative beige to a cool high-end neutral;
the working surface stays white and sits a hair above it.

### Lines

| Token            | Value     | Use                                               |
| ---------------- | --------- | ------------------------------------------------- |
| `--line-soft`    | `#eceef2` | Dividing one thing from the next.                 |
| `--line-default` | `#dfe3e9` | The edge of a card, the rule under a page header. |
| `--line-strong`  | `#c3c9d3` | The edge of something you can type in or press.   |

### Text

| Token              | Value     | Use                                                 |
| ------------------ | --------- | --------------------------------------------------- |
| `--text-primary`   | `#131820` | The answer, and every heading.                      |
| `--text-secondary` | `#4a5261` | Supporting prose.                                   |
| `--text-muted`     | `#6b7484` | Labels, column headers, footnotes.                  |
| `--text-faint`     | `#9aa3b2` | Decorative only — a chevron, a separator. Never text. |
| `--text-inverse`   | `#ffffff` | On a filled accent or the rail.                     |

### Intent

Each intent has a solid colour for text and a soft one for a fill. Status
colour always reinforces a word, never replaces it.

| Intent    | Solid     | Soft      | Means                                              |
| --------- | --------- | --------- | -------------------------------------------------- |
| `accent`  | `#2454d0` | `#e9effc` | The product's one action colour. Also `info`.       |
| `success` | `#157347` | `#e3f4ea` | Done, given, cleared, available, approved.          |
| `warning` | `#8a5300` | `#fbf1dc` | Waiting on somebody, held, past due but not failed. |
| `danger`  | `#a8231a` | `#fbe9e7` | Refused, expired, cancelled, blocked, a loss.       |

The accent is used with restraint: the one primary button on a surface, the
selected tab, a record link, a focus ring. It is not sprayed across headings
and icons.

### Navigation rail

| Token                | Value                    | Use                                    |
| -------------------- | ------------------------ | -------------------------------------- |
| `--nav-bg`           | `#0e1422`                | The rail. Also `--ink`.                 |
| `--nav-bg-hover`     | `rgb(255 255 255 / 6%)`  | A hovered item.                         |
| `--nav-bg-selected`  | `rgb(255 255 255 / 11%)` | The current section.                    |
| `--nav-line`         | `rgb(255 255 255 / 8%)`  | Dividers inside the rail.               |
| `--nav-text`         | `#e6e9f0`                | Item labels.                            |
| `--nav-text-strong`  | `#ffffff`                | The current item, the brand, the name.  |
| `--nav-text-muted`   | `#97a1b6`                | Group labels, the person's roles.       |
| `--nav-accent`       | `#93b3ff`                | The current item's bar and icon.        |
| `--nav-focus`        | `#d2ddff`                | Focus ring on the dark rail.            |

**The ink hairline is the product's signature.** `--ink` is the rail's
colour, and it reappears as the two-pixel rule over a command surface: the
one place the navigation's material shows up inside the working area, and the
reason the most important block on a page reads as part of the same object
the reader navigated with. It is the only gradient in the stylesheet.

### Spacing, radius, elevation, layout, motion

`--space-1` … `--space-8` = `0.25 / 0.5 / 0.75 / 1 / 1.5 / 2 / 3 / 4 rem`.

`--radius-control: 6px` for anything you type in or press; `--radius-card:
12px` for a surface; `--radius-tag: 5px` for a badge; `--radius-pill` for a
chip.

`--shadow-xs` for a card at rest, `--shadow-md` for a menu or dialog,
`--shadow-lg` for a drawer. Elevation is nearly flat on purpose.

`--sidebar-width: 16rem`, `--sidebar-collapsed-width: 4.25rem`,
`--context-bar-height: 3.25rem`, `--content-max: 112rem`, `--content-pad:
2rem`, `--content-gap: 1.5rem`, `--prose-max: 60rem`, `--drawer-width: 64rem`,
`--drawer-width-narrow: 46rem`, `--control-height: 2.25rem` (`-sm: 1.75rem`,
`-lg: 2.5rem` for form fields).

`--motion-fast: 120ms` for hover and colour, `--motion-base: 180ms` for a
drawer, a dialog or a menu entering. Nothing bounces, nothing counts up, and
`prefers-reduced-motion` reduces all of it to nothing.

---

## 5. Typography

Typography is the main reason the previous edition could feel institutional,
and the main thing this edition changed.

Two families: `--font-sans` (Inter where installed, otherwise the system
stack) for everything a person reads, figures included, and `--font-mono` for
an identifier a person matches against a document — a unit reference, a
contract number, a receipt. Figures are sans with tabular digits (`.num`,
`.figure`, every metric and position value) so they line up down a column
without looking like code.

Body text is `--text-base` (14px). This is a register-heavy product used at a
desk; a 16px body would push a fourteen-column register off the screen.
Registers keep their density. Hierarchy comes from the levels above the body,
not from making everything larger.

| Role                    | Token               | Size       |
| ----------------------- | ------------------- | ---------- |
| Project plate title     | `--title-plate`     | 1.875rem   |
| Page title              | `--title-page`      | 1.5rem     |
| Record title            | `--title-record`    | 1.625rem   |
| Section/card title      | `--title-section`   | 1rem       |
| The figure a page is for| `--metric-hero-lg`  | 2.5rem     |
| A position figure       | `--metric-hero`     | 2rem       |
| A metric                | `--metric`          | 1.375rem   |

**Fewer tiny uppercase labels.** Column headers, metric labels, position
labels, key/value terms, record facts and section headings are set in
sentence case at `--text-xs` or `--text-sm`, semibold, muted. Uppercase
tracking is reserved for the genuine eyebrows — the rail's group labels, a
page's or a record's eyebrow, the brand line — where it says "this is chrome"
and nothing else. A section heading is now a heading: sentence case, primary
colour, clearly a level above the rows beneath it.

---

## 6. The shell

```
.app                                data-rail="auto | expanded | collapsed" · .app-narrow
├── .sidebar                        the rail
│   ├── brand
│   ├── ProjectSwitcher             inside a project; "Projects" outside one
│   ├── nav groups                  Overview · Development · Commercial · Delivery · Finance · Governance
│   └── footer                      who you are · Settings · Sign out
├── .context-bar                    menu (phone) · rail toggle · breadcrumbs · status · base currency
└── .app-content                    PageHeader, then the page
```

**The rail is the developer's departments.** Development (Land, Permits,
Inventory), Commercial (Pricing, Sales & Legal, Payment Plans, Collections),
Delivery (Construction), Finance (Unit Economics, Cashflow), Governance
(Documents, Access), with Overview on its own at the top. The order is the
lifecycle of a development and the guard test pins it. A group with nothing
the reader may open is not drawn.

**The project switcher is first-class.** It sits under the brand, shows the
project's code, status and city, and opens a searchable menu of the projects
the reader may access. Choosing one keeps the current section.

**The context bar is white and quiet.** Breadcrumbs (`Projects / Galini Blu /
Inventory` — the project's name, because a name is what a person recognises),
the project's status badge and its base currency. The page header underneath
says where you are in words; the bar keeps that visible while a register
scrolls. It is not a second menu.

**Three rail states, two signals.** `data-rail` carries the person's
preference (`auto`, `expanded`, `collapsed`; kept in `localStorage` under
`reach.rail`, read inside a `try`). `app-narrow` carries the viewport's
verdict below 75rem. The stylesheet draws the collapsed rail from one set of
rules that name the sticky rail — so the phone's navigation drawer, which is
the same content inside the same shell, keeps its labels. Collapsed items
show their label as a tooltip and keep their accessible name.

**Below 64rem the rail becomes a drawer.** The context bar grows a menu
button; the rail opens as a focus-trapped `dialog` over a scrim, closes on
Escape, on the scrim and on choosing a destination, and is mounted only while
open.

**Routing is the query string.** `/projects/?project=<id>&section=<key>` and
`/settings/?section=<key>`; `projectHref` and `settingsHref` in
`components/shell/navigation.ts` are the only places those strings are built.

### Visibility mirrors the server

`lib/roles.ts` holds the same sets as `app/modules/*/permissions.py`, and
every navigation item, section, record tab, record headline and request is
gated by one of them. The guard test compares the construction and cashflow
reader sets against the backend by reading both files, checks that every
gated navigation item names its reader set, and checks that every summary the
command centre requests is gated on the matching flag.

---

## 7. Page anatomy

```
PageHeader        eyebrow · title · status · subtitle · facts · actions
Command           the one answer the page exists to give        (Card tone="command")
Counts            a compact ruled strip, not a row of cards      (StatStrip)
DataToolbar       search · two or three filters · count · clear  (framed)
Register          Card flush > TableScroll fixedFirst
```

**`PageHeader` composes title, status, description, facts and actions.** The
title is strong; the page's current state sits beside it as a badge where a
page has one; the primary action is visibly primary and there is at most one;
everything else on the right is quiet. `meta` carries the small facts that
identify the place — a code, a currency, a date — never figures. `compact`
trims the chrome on register-heavy pages.

**Exactly one `<h1>` per screen**, in the header. Cards use `<h2>`, sections
inside them `<h3>`.

### The command surface

A page has one answer, and the answer is a `Card tone="command"`: the cool
near-white ground, the ink hairline, and inside it a `Position` — two to four
reported figures set large with the label **beneath**, the way a tear sheet
sets them — over a `PositionSupport` line of the facts that produced them.
That inversion is the whole difference between a dashboard statistic and a
financial statement: the number is what the reader came for, and the word
only confirms which number it is.

```
-427.9618%          JOD -7,266,150.00        -81.0592%
Margin              Profit                    Return on cost
Minimum 18%         After finance
────────────────────────────────────────────────────────────
Contracted 1 of 12 units   Revenue JOD 1,697,850.00   Total cost JOD 8,964,000.00
```

Do not put five equal KPI cards at the top of a screen. Counts belong in a
`StatStrip` — a ruled band of four or five figures with hairlines between —
unless one of them genuinely deserves to be the position.

### Figures are the server's

Every figure in a `Metric`, a `Position`, a `StatStrip`, a `Breakdown`, a
`Waterfall`, a `Distribution` or a `Meter` arrived on the request that drew
it. The guard test reads the representative screens and fails on
`parseFloat`, `toFixed`, `Intl.NumberFormat`, `.reduce(` and arithmetic on a
response field, and reads every `PositionFigure` on the overview for an
operator.

---

## 8. Registers

Registers are the product's centre of gravity, and PR-V2-00 made them read as
a premium operating ledger rather than a spreadsheet clone.

- **The identity cell anchors the row.** `IdentityCell` sets the reference a
  person says out loud (`A-304`, `SPA-000147`, `Rana Haddad`) as the link that
  opens the record, with the two or three words that say which record it is
  beneath. `PlaceCell` says where a record sits in the development.
- **The header is a label strip in sentence case**, muted, with a single rule
  beneath it. No uppercase tracking, no tinted band.
- **The only lines are the hairlines between rows.** No cell borders, no
  grid.
- **Figures sit right, tabular, and never wrap.** `.num` on the header and
  the cell. A figure broken across two lines is misread as two figures.
- **Density is the register's.** Rows are 0.625rem of padding; `compact`
  steps them down for a schedule or a history. Command surfaces, record
  headers and forms get more room; registers do not.
- **Row states.** Hover tints the row; the row whose record is open carries an
  accent rail and the selected ground; a row the server flagged carries a
  warm rail and nothing else; a chevron appears at the far right on hover.
- **Status is compact.** A `Badge` for the state the row is about, a
  `StatusDot` for every other state on the row, plain text for a fact that
  is not a state. A register is never a bag of coloured pills.
- **Actions do not own a column.** A row's action is small and quiet, and
  the identity link is the way in.
- **Wide is fine.** A register scrolls inside `TableScroll` with the identity
  column pinned; the page body itself never scrolls sideways at any width,
  and the walkthrough asserts it at 1600, 1440, 1280, 1024, 768 and 390.
- **A footnote under a register** (`.table-foot`) sits inside the flush card
  with a rule above it, never as an inline-styled paragraph.

### The toolbar

`DataToolbar framed` is one instrument: search on the left, the two or three
filters that narrow the register, the count of what survived, and the way to
clear everything. A filter that is currently narrowing the register is tinted
(`ToolbarFilter active`) so a reader who cannot find a row can see why. Below
60rem the instrument stacks; nothing in it takes a height it was not given.
It is not a query builder and will not become one.

---

## 9. The record file

A record — a unit, a deal, a payment plan, a collections account, a contract,
a certificate, a permit, a new project — opens over the register that led to
it, in a `Drawer`. Opening one should feel like opening a file, not opening a
modal full of forms.

```
Drawer
├── identity      eyebrow · title · where it is · state          (left)
├── headline      the one value the record is about              (right, large)
├── actions       the one or two things this record invites      (right)
├── facts strip   three or four supporting figures, on the command ground
├── sections      the departments, as a real tablist
└── body          the selected section, scrolling under the fixed header
```

**The headline is role-shaped, and so is the strip.** A unit's headline is
its current list price, with the version and basis in words beneath — present
only for a role the server answers with the price, because the price is
requested only for that role. Legal and Collections open the same file with
no headline and nothing hidden. The facts strip carries the areas, the margin
for economics readers, the outstanding balance for collection readers. A
failed request is said as a failure, never drawn as "not priced".

**Unit 360 is the flagship.** `A-101` · `2BR · 2 bedroom · Phase P1 /
Building A / Floor 01` · Contracted · Releasable, with `JOD 214,912.50 ·
Current list price · v1 · ex tax` beside it and `Edit unit` for a role that
may. Then internal area, weighted saleable area, attached parking, margin and
outstanding on the strip; then Overview, Areas & features, Pricing, Sales &
legal, Collections, Economics, Release and History. The Overview's four
status dimensions sit side by side on one ruled band, never merged and never
boxed. Nothing in the file calculates, and it does not yet orchestrate
Buyer → Reserve → Sell: that is PR-V2-04 and PR-V2-05, and this file is the
visual pattern they will build on.

**A new record is a file too.** Creating a project opens a narrow drawer
over the portfolio register with a grouped form inside, so the register stays
where it was.

**Below 64rem every drawer takes the whole screen**, the headline drops under
the identity, and the way back is a button at the top left.

---

## 10. Status presentation

Not every status is a pill. Three treatments, by importance:

| Treatment            | For                                                   | Primitive     |
| -------------------- | ----------------------------------------------------- | ------------- |
| Primary current state| The state a surface is about: commercial status on a unit, sale status on a deal, a project's lifecycle state beside the page title | `Badge`       |
| Secondary fact       | Every other state on the same row or record           | `StatusDot`   |
| A fact that is not a state | A version, a date, a basis                       | plain text    |

Status words live with the module that owns them, next to the labels
(`inventory/statusLabels.ts`, `sales/labels.ts`, `payments/labels.ts`,
`collections/labels.ts`, `economics/labels.ts`, `construction/labels.ts`,
`cashflow/labels.ts`). A status the interface has not been taught falls
through unchanged and is drawn neutral. The two that decide something rather
than name it — `varianceTone` (positive is over budget) and `headroomTone`
(negative is committed past the authorisation) — live in one place because a
second copy would eventually disagree.

A unit's four dimensions — commercial, legal, collection, delivery — are
always shown side by side and never merged.

---

## 11. Actions

Every surface understands three levels:

| Level        | Treatment                                    | Rule                                        |
| ------------ | -------------------------------------------- | ------------------------------------------- |
| Primary      | `Button variant="primary"` — filled accent   | One per surface. Rare.                      |
| Secondary    | `default` — white, outlined; `quiet` beside data | Everything else.                        |
| Destructive  | `danger` — an outline, never a fill          | Never visually competes with the happy path. |

`link` is a record identifier that opens the record: it reads as data and
behaves as a link. In-table actions are `small`, and `quiet` where they sit
beside data they must not outweigh. Major actions live in the page header or
the record header, never scattered across unrelated cards.

---

## 12. Forms

```
Form
├── FormSection        a titled group, ruled from the next: Identity · Financial basis · Location
│   └── FieldRow       two, three or four fields side by side; one column on a phone
│       └── Field      label · control · hint · error · "Optional"
└── FormActions        a rule, the primary action, and the way out
```

- Labels are strong and primary-coloured; hints are muted and used only where
  a label alone would not say enough; placeholder text never acts as a label.
- Everything is required unless marked `Optional`. That is the one marker.
- Controls in a form are `--control-height-lg`; controls in a toolbar or a
  schedule keep their compact height.
- Two columns where the content genuinely benefits; a form does not run as a
  single column down a desktop screen.
- A group is a rule and a title (`FormSection`, `SubPanel`), never a bordered
  panel around every field group.
- `MoneyInput` shows the record's currency code beside the control and keeps
  the exact string typed; `RateInput` shows `%` and the caller sends the
  server's fraction through `fractionFromPercent`, a string operation.
- Validation is the server's. The message on refusal is the server's own
  words, in a `Notice` tied to the form that failed.

---

## 13. Dialogs

`ConfirmDialog` (`alertdialog`, focus lands on the safe button) for the
irreversible; `PromptDialog` (labelled, with an optional description of what
the reason is for) for the one reason an action needs; `FormDialog` for the
several things an attestation needs. All three sit on the shared overlay
helper: focus moves in, Tab stays inside, Escape closes the topmost overlay
only, focus returns to the control that opened it. A dialog's actions sit
under a rule. No screen uses `window.prompt`, `window.confirm` or
`window.alert`; the guard test reads for them.

---

## 14. Empty, loading, denied, failed

`lib/answer.ts` names the five ways one request answers a screen — `off`,
`loading`, `ready`, `denied`, `failed` — and every card on the command
centre and every role-shaped section of a record is one `Answer`.

**Empty states explain.** `EmptyState` says what is missing, why it matters
and what to do, with an icon from the product's own set and an action where
one exists: "No payment plan yet", never "0 records". It is not boxed: an
empty state is an absence, and a bordered absence reads as a broken widget.

**Loading states have the shape of what is coming.** `Loading` draws the
silhouette of a page header (`header`), a metric strip (`metrics`), a
register (`rows`), a record file (`record`) or a page (`page`), so the page
does not jump when the answer arrives. No animation library; the pulse is one
keyframe and reduced motion removes it.

**Errors are calm and local.** A `Notice tone="error"` is tied to the surface
that failed and carries the server's own words. A failed subsection gets a
small notice, never a red page. `denied` is drawn as "Not available to your
role", never as a blank and never as a row of zeros; "withheld" and "not
recorded" must never look the same.

---

## 15. The command centre

The project Overview is a developer's command centre, read top to bottom:

1. **Context** — `ProjectPlate`: name, developer, place (with the map link
   beside it, never as the name), then code, status, type, programme,
   currency and manager as inline facts. No figure appears here.
2. **Position** — the command surface: margin, profit and return on cost
   where Finance has given a basis; units, available, contracted and
   contracted value where it has not.
3. **Attention** — beside the position, a list of the counts the server
   already reports as problems, in lifecycle order, each with its way in.
   Permits, pricing, sales, collections, construction and economics all
   contribute. Nothing is scored or ranked.
4. **Departments** — one card, four ruled sections: Commercial (inventory,
   sales, pricing), Development (consents, programme), Delivery (the build's
   variance at completion, control budget, commitment, certified to date —
   for construction readers), Finance (usable cash, restricted cash, funding
   required — for cashflow readers). Each has one "Open".
5. **Collections** — per currency, never totalled across them, with the
   ageing bands the server named.

Every section is requested once, only on behalf of a role the server answers,
and the guard test pins each request to its reader flag.

---

## 16. Primitives

Imported from `@/components/ui`. One name per primitive; there are no
aliases, and the guard fails the build on `Panel`, `Stat`, `StatRow`,
`FilterBar` or any `Card2`-shaped name.

| Primitive                                   | What it is for                                                         |
| ------------------------------------------- | ---------------------------------------------------------------------- |
| `PageHeader` (`status`, `meta`, `compact`)  | Where you are, where it stands, what you can do. One per screen.        |
| `SectionHeader`                             | A sentence-case division inside a card or a record, with one action.    |
| `Card` (`tone`, `flush`) / `SubPanel`       | The one surface, and the ruled band inside it.                          |
| `Tabs` / `TabPanel`                         | Sections of a place. A real tablist; arrow keys work.                   |
| `Drawer` (`headline`, `facts`, `actions`, `narrow`) | A record file opened over the register it came from.            |
| `Button` / `ButtonRow`                      | `primary`, `default`, `quiet`, `danger`, `link`.                        |
| `Field` / `FieldRow` / `FormSection`        | A control with its label; controls side by side; a titled group.        |
| `MoneyInput` / `RateInput`                  | Money with its denomination; a rate typed as a percentage.              |
| `FormActions` / `StickyActions`             | The way a form ends.                                                    |
| `DataToolbar` / `ToolbarFilter`             | The instrument that narrows a register.                                 |
| `TableScroll` (`fixedFirst`, `compact`)     | A wide register that scrolls inside itself.                             |
| `IdentityCell` / `PlaceCell`                | A register row's anchor, and where it sits.                             |
| `KeyValueGrid` / `KeyValue`                 | Labelled facts about one record.                                        |
| `Metric` / `MetricGroup`                    | One reported number, labelled; a strip of them.                         |
| `Position` / `PositionFigure` / `PositionSupport` / `PositionSupportItem` | The figures a page is opened for, label beneath. |
| `StatStrip` / `StatStripItem` / `StatStripNote` | Four or five counts on one ruled band.                             |
| `Breakdown` / `BreakdownRow`                | The parts of a total, with a leader to each amount.                     |
| `Waterfall` / `WaterfallRow`                | A sequence the server applied to reach a figure.                        |
| `Distribution` / `DistributionBand`         | A balance across the bands the server aged it into.                     |
| `Meter`                                     | A percentage the server reported, drawn at the width it reported.       |
| `InlineMeta` / `InlineMetaItem`             | Small facts in a line: "Code GB-01 · Status Active".                    |
| `ExternalLink`                              | A destination outside the product, named rather than addressed.         |
| `Badge` / `StatusDot`                       | The state a surface is about; every other state.                        |
| `Notice`                                    | Something the system needs to say, tied to where it happened.           |
| `EmptyState` (`icon`, `compact`) / `Loading` (`shape`) | Nothing here yet; waiting, in the shape of what is coming.  |
| `Timeline` / `TimelineItem` / `Steps`       | What happened, in order; the named steps a record passes, as one track. |
| `ConfirmDialog` / `PromptDialog` / `FormDialog` | Confirm the irreversible; collect a reason; collect an attestation. |
| `Icon`                                      | Hand-drawn inline SVGs. No icon package.                                |

### Retired in PR-V2-00

`Panel` (was `Card`), `Stat` and `StatRow` (were `Metric` and
`MetricGroup`), `FilterBar` (was the pre-toolbar strip), the project tiles,
the twelve-column grid's unused spans, and the "refinements" section that
re-declared thirteen selectors at the foot of the stylesheet. The stylesheet
is one layer again: no top-level selector is declared twice, every class it
declares is used, and every class a component uses is declared. The guard
checks all three.

---

## 17. Numbers, money and dates

**Calculation and presentation are different things, and only one of them is
allowed here.** `lib/format.ts` is the only place presentation happens:

- **Money** — `money(value, code)` turns the server's exact decimal string
  into `JOD 228,000.00`: digits grouped, sign kept, every decimal preserved,
  the real currency code prepended. Never `Number()`, `parseFloat` or
  `Intl.NumberFormat`. No rounding, no scale change, no FX.
- **Denomination is resolved, never assumed.** Every record that carries
  money carries its own `currency_id`; `useCurrencyCode` resolves it. An id
  the map cannot resolve renders undenominated, never labelled with a guess.
  Amounts in different currencies are never added.
- **Rates** are shown through `percent()`, a string operation.
- **Business dates** render as `30 Aug 2026` from calendar components, never
  through a JavaScript `Date`.
- **Financial presentation** is statement-like: strong primary figures,
  tabular numerics, clean alignment, the denomination beside every amount,
  the basis in words beneath. A CFO should be able to screenshot a position
  and understand it immediately. No donuts, no arbitrary progress bars, no
  chart furniture.

---

## 18. Interaction and motion

Records open over the register, not under it. Progressive disclosure is by
section, not by accordion. Confirmation is reserved for the irreversible.
Affordances mirror the server and never replace it.

Motion is restrained: the rail's width, a drawer's entrance, a dialog
settling, a menu dropping, hover and focus transitions, the selected tab's
underline. No bouncing, no springs, no animated counters, no moving
gradients. Premium software feels fast because nothing gets in the way.

---

## 19. Iconography

`Icon` is a map of hand-drawn stroke paths on a 16×16 grid, one per
navigation item and control, drawn at a consistent weight and hidden from
assistive technology because an icon here only ever repeats something the
adjacent text already says. Adding a glyph is adding a path. There is no icon
package, and the guard test reads `package.json` to make sure none arrives.

---

## 20. Responsive behaviour

Desktop is primary. The product is validated at six widths.

| Width          | Behaviour                                                                          |
| -------------- | ---------------------------------------------------------------------------------- |
| ≥ 75rem (1200) | Full rail with labels. Drawers at `--drawer-width`.                                 |
| 64–75rem       | Rail collapses to icons (`auto`); labels become tooltips.                          |
| < 64rem (1024) | Rail becomes a drawer behind a menu button. Record drawers take the full width.     |
| < 60rem        | The framed toolbar stacks.                                                         |
| < 48rem (768)  | Single-column forms and key/value grids; the department band stacks; the record headline drops under the identity. |
| < 34rem (544)  | Phone: compact padding; the stat strip and the standing band wrap as pairs.        |

Phone does not reproduce a fourteen-column register; it keeps the register
scrolling inside itself with the identity pinned, keeps the primary action
reachable, and opens every record full-screen. There is no separate mobile
application.

---

## 21. Accessibility

- One `<h1>` per screen; headings descend without skipping.
- The rail is a `<nav>` with a label; the current item carries
  `aria-current="page"`; the breadcrumbs are a `<nav aria-label="Breadcrumb">`
  around an ordered list; the collapsed rail keeps every item's name.
- Tabs are a real `tablist` with arrow, Home and End keys, roving `tabIndex`,
  namespaced ids, and the selected tab kept in view.
- Drawers, the mobile navigation, the switcher menu and dialogs are
  `dialog`/`alertdialog` with `aria-modal` and an accessible name, on the
  shared overlay helper: focus in, Tab contained, Escape closes the topmost
  only, focus returned on close.
- Every table has a hidden `<caption>` and scoped headers; `TableScroll` is
  focusable so a keyboard can scroll it.
- Every control is at least 24px tall; controls in forms are 40px.
- Focus is always visible: a 2px accent ring on the light surface, a light
  ring on the dark rail.
- Text and its background meet WCAG AA on every token pair used together.
- Colour is never the only carrier of meaning.
- `prefers-reduced-motion` removes all transitions and animation.

---

## 22. What this system deliberately does not have

No component library, no CSS framework, no CSS-in-JS, no icon package, no
chart library and no charts, no table, form, date or animation library, no
client state library, no dark theme, no FX, no health scores, no trends, no
projections, no command palette, no generic workflow engine. Adding any of
them is a decision with a cost, argued for in a pull request of its own.

The frontend is a **static export** served by FastAPI from `frontend/out`.
There are no server components, no server actions, no SSR and no dynamic
route segments.

---

## 23. Extending it

1. Compose from the primitives first. Most "new components" are a
   `PageHeader`, a command `Card` with a `Position`, a `StatStrip`, a
   `DataToolbar` and a flush `Card` around a `TableScroll`.
2. If a genuinely new primitive is needed, add it to `components/ui/`, export
   it from `components/ui/index.ts`, give it one responsibility and one name.
   Never a second version of an existing one.
3. Style it with tokens. If a token is missing, add it to `:root` — never a
   literal colour, size or duration in a rule, and never an inline style.
4. One rule per selector. A variation is a modifier class, not a later copy.
5. Keep business rules out of it. A primitive that knows what a price is, or
   who may approve one, is in the wrong place.
6. Gate by role before you fetch. A new module gets a set in `lib/roles.ts`
   that mirrors its `permissions.py`, a `visible` rule on its navigation
   item, and `useAnswer` around every request a role might be refused.
7. Never total, convert or derive a figure in the browser. If the screen
   needs a number the API does not return, the API grows the number.
8. Run the checks: `npm run lint`, `npm run build`,
   `pytest -q tests/test_product_experience.py`, and the browser walkthrough
   — every role, six widths, every drawer — reading the console, the failed
   requests and the overflow report before calling anything done.
