# UX System 2.0 — Reach Developments Station

The product's design system, second edition: one light working surface, one
dark navigation rail, one token layer, and a small set of hand-written
primitives. No component library, no icon package, no CSS framework, no chart
library, no client state library.

The first edition (PR-UX-01) made the product consistent. This edition
(PR-UX-02) makes it a workspace: a place a developer's teams live in all day,
where a project is read at a glance, a module is one click away, and a record
opens as a file with its own headline figures. The business truth underneath
did not move; the way in was rebuilt around it.

Everything here lives in a few places:

| What                          | Where                                              |
| ----------------------------- | -------------------------------------------------- |
| Tokens and classes            | `frontend/src/app/globals.css`                     |
| Primitives                    | `frontend/src/components/ui/`                      |
| Shell, rail, switcher, crumbs | `frontend/src/components/shell/`                   |
| Role sets the shell mirrors   | `frontend/src/lib/roles.ts`                        |
| One request, five answers     | `frontend/src/lib/answer.ts`                       |
| Presentation of figures       | `frontend/src/lib/format.ts`, `frontend/src/lib/currency` |
| Project command centre        | `frontend/src/components/dashboard/`               |

If a screen needs something this document does not describe, the answer is
almost always a new composition of what is here — not a new dependency.

---

## 1. What this product is, and what that means for its interface

This is the record of what a real estate developer owns, what it is selling,
what it has agreed, and what it is owed. People use it to answer questions they
will later have to defend: to a board, to a lender, to a buyer's lawyer, to an
auditor.

Four consequences run through every decision below.

**Nothing on screen may be invented.** Every figure, status, blocker, gate and
total is a value the API returned on that request. The browser lays out and
labels; it never calculates a price, a discount, a tax, a margin, a total, an
allocation, a release eligibility or an approval requirement. There is exactly
one implementation of each of those, and it is on the server. A second one in
React would eventually disagree with it, and the disagreement would be
discovered by somebody signing a contract.

**Empty space beats a plausible number.** There are no placeholder cards, no
sample series, no charts drawn from nothing, no "0%" standing in for "not
measured". Where a total cannot honestly be produced — a project whose
contracts are in two currencies — the screen says so and shows nothing.

**What a role may not read, the browser does not ask for.** Navigation,
sections and record tabs mirror the backend's permission sets. A Sales Advisor
has no Unit Economics entry, no Economics tab on a unit, no margin in a unit's
header and no request to the economics endpoints at all. Hiding a figure after
fetching it is not restriction; it is a leak waiting for a refactor.

**A word carries the meaning; colour only repeats it.** Nothing on any screen
is understood by hue alone. Status is always written out, and the badge or dot
behind it is a skim aid.

---

## 2. Theme

**A light workspace and a dark rail.** `html { color-scheme: light; }`, and
there is no `prefers-color-scheme` rule anywhere in the stylesheet.

The working surface is light because it gets printed, screenshotted into board
packs and shared as evidence, and a document that looks different on the
reviewer's machine than on the preparer's is a document somebody has to
explain. The rail is dark because it is chrome, not content: it frames the
work without competing with it, and it reads as the same object whether the
person is on Inventory or on Collections.

A dark theme is a real piece of work — every token, every status colour, every
contrast pair — and half of one is worse than none. If one is ever added, the
token layer is where it goes: redefine the tokens in section 3 under both
`@media (prefers-color-scheme: dark)` and an explicit `[data-theme="dark"]`,
and change nothing else.

---

## 3. Tokens

All tokens are CSS custom properties on `:root`. Components never hard-code a
colour, a radius, a spacing step or a duration.

### Canvas and surfaces

| Token                 | Value     | Use                                                  |
| --------------------- | --------- | ---------------------------------------------------- |
| `--canvas`            | `#f4f4f1` | The warm page behind everything.                      |
| `--surface`           | `#ffffff` | Cards, the context bar, drawers, dialogs.             |
| `--surface-secondary` | `#f8f8f6` | Forms, filter strips, facts strips, nested regions.   |
| `--surface-hover`     | `#f1f2ef` | Row and control hover.                                |
| `--surface-selected`  | `#eaf0fc` | The selected row, tile or segment.                    |

### Lines

| Token            | Value     | Use                                               |
| ---------------- | --------- | ------------------------------------------------- |
| `--line-soft`    | `#ebebe7` | Dividing one thing from the next.                 |
| `--line-default` | `#dcddd8` | The edge of a card or a strip.                    |
| `--line-strong`  | `#c1c4c9` | The edge of something you can type in or press.   |

### Text

| Token              | Value     | Use                                         |
| ------------------ | --------- | ------------------------------------------- |
| `--text-primary`   | `#141922` | The answer.                                 |
| `--text-secondary` | `#4b5462` | Supporting prose, field labels.             |
| `--text-muted`     | `#676f7d` | Column headers, term labels, footnotes, placeholders. |
| `--text-faint`     | `#9aa1ad` | Decorative only — a muted dot, a rule. Never text. |
| `--text-inverse`   | `#ffffff` | On a filled accent.                         |

### Intent

Each intent has a solid colour for text and a soft one for a fill.

| Intent    | Solid     | Soft      | Means                                              |
| --------- | --------- | --------- | -------------------------------------------------- |
| `accent`  | `#2454d0` | `#e8eefc` | The product's one action colour. Also `info`.       |
| `success` | `#177245` | `#e3f3ea` | Done, given, cleared, available, approved.          |
| `warning` | `#8a5300` | `#fbf0dc` | Waiting on somebody, held, past due but not failed. |
| `danger`  | `#a3221a` | `#fbe9e7` | Refused, expired, cancelled, blocked, a loss.       |

`--accent-hover` (`#1b43ad`) is the pressed and hovered accent;
`--accent-ring` is the focus ring.

### Navigation rail

| Token                | Value                   | Use                                     |
| -------------------- | ----------------------- | --------------------------------------- |
| `--nav-bg`           | `#131a2b`               | The rail.                               |
| `--nav-bg-hover`     | `rgb(255 255 255 / 6%)` | A hovered item.                         |
| `--nav-bg-selected`  | `rgb(255 255 255 / 11%)`| The current section.                    |
| `--nav-line`         | `rgb(255 255 255 / 9%)` | Dividers inside the rail.               |
| `--nav-text`         | `#e7eaf1`               | Item labels.                            |
| `--nav-text-muted`   | `#98a2b8`               | Group labels, the person's roles.       |
| `--nav-accent`       | `#8db0ff`               | The current item's bar and icon.        |
| `--nav-focus`        | `#cfdcff`               | Focus ring on the dark rail.            |

### Spacing, radius, elevation

`--space-1` … `--space-8` = `0.25 / 0.5 / 0.75 / 1 / 1.5 / 2 / 3 / 4 rem`.

`--radius-control: 6px` for anything you type in or press, `--radius-card:
10px` for a container, `--radius-tag: 5px` for a badge, `--radius-pill: 999px`
for a chip.

`--shadow-xs` for a card at rest, `--shadow-sm` for a raised block,
`--shadow-md` for a menu or dialog, `--shadow-lg` for a drawer. Elevation is
nearly flat on purpose: the hierarchy comes from spacing and rules, not from
stacked shadows.

### Typography

Two families: `--font-sans` (the system stack) for everything a person reads,
figures included, and `--font-mono` for an identifier a person matches
against a document — a unit reference, a contract number, a receipt number.
Figures are sans with `font-variant-numeric: tabular-nums` (`.num`, `.figure`,
the metric value) so they line up down a column without looking like code.

Scale, in rem: `--text-2xs` `.6875` · `--text-xs` `.75` · `--text-sm` `.8125` ·
`--text-base` `.875` · `--text-md` `.9375` · `--text-lg` `1.0625` · `--text-xl`
`1.25` · `--text-2xl` `1.5` · `--text-3xl` `1.75`.

Named sizes for the things that carry hierarchy: `--title-page` `1.375rem`,
`--title-record` `1.5rem`, `--title-section` `.9375rem`, `--metric`
`1.375rem`, `--metric-lg` `1.75rem`.

Body text is `--text-base` (14px). This is a register-heavy product used at a
desk; a 16px body would push a fourteen-column register off the screen.

### Layout and motion

`--sidebar-width: 16.5rem`, `--sidebar-collapsed-width: 4.5rem`,
`--context-bar-height: 3.25rem`, `--content-max: 118rem`, `--content-pad:
1.5rem`, `--content-narrow: 26rem` (sign-in), `--drawer-width: 62rem`,
`--drawer-width-narrow: 46rem`.

`--motion-fast: 120ms` for hover and colour, `--motion-base: 160ms` for
anything larger, `--ease` for both. The rail's width and a drawer's entrance
are the only things that move; `prefers-reduced-motion` reduces everything to
nothing.

---

## 3a. Surfaces

The shell frames the work. This is the work itself, in five weights. A surface
earns its treatment from what it holds, never from a wish to be noticed, and a
page has at most one of the strong ones — giving everything a tone is the same
as giving nothing one.

| Surface | Where | Treatment |
| --- | --- | --- |
| **Command** | The one thing a page exists to answer: a project's position, a pricing policy, a collections balance, a unit economics result. | `Card tone="command"` — a cool near-white ground and a two-pixel hairline of the navigation rail's own ink across the top. |
| **Operational** | Ordinary workflow: a commercial position, a development summary, a form that opened. | The plain `Card`. Most blocks are this. |
| **Data** | A register. | `Card flush` around a `TableScroll`: the frame recedes and the rows carry the page. |
| **Attention** | Something owed, blocked or past its date. | `Card tone="attention"` — a narrow warm rail and the faintest tint. Never a red page. |
| **Record** | A unit, a deal, a plan, a version. | The `Drawer`, opened over the register that led to it, with a facts strip on the command ground. |

`tone="subtle"` is the fifth, and the quietest: a supporting block beside
something that matters more.

**The ink hairline is the product's signature.** The rail is `--nav-bg`, and the
same colour reappears as the rule above a command surface. It is the one place
the navigation's material shows up inside the working area, and it is what
makes the most important block on a page read as part of the same object the
reader navigated with rather than as a card that happens to be there.

### Figures are set like a tear sheet

A reported figure that a page is opened for is large, tightly tracked, tabular,
and carries **its label underneath**. That inversion is the whole difference
between a dashboard statistic and a financial statement: the number is what the
reader came for, and the word only confirms which number it is.

Ordinary metrics keep the label above the value. The two treatments are how a
page says which of its figures is the answer and which are the supporting cast.

```
37.3044%            JOD 6,975,559.30        59.5009%
MARGIN              PROFIT                  RETURN ON COST
Minimum 18%         After finance
──────────────────────────────────────────────────────────────
Revenue JOD 18,699,007.38   Total cost JOD 11,723,448.08   Covered 118 of 126
```

`Position` lays those out; `PositionSupport` is the ruled line of facts beneath
them. `Position compact` steps the figures down for a composition of four or
five money amounts, where four full-size ones would wrap.

### The compositions, and what each is for

- **`StatStrip`** — four or five counts in one band: "126 Units · 88 Available ·
  6 Held · 10 Unreleased". Counts are not findings, and four cards for four
  integers is four times the furniture the information deserves.
- **`Breakdown`** — the parts of a total, each with a dotted leader to its
  amount and the server's own total ruled off underneath. The leader is a
  financial-document convention, and it is why the block reads as a statement
  rather than as two columns that happen to be near each other.
- **`Waterfall`** — a sequence the server applied in order to reach a figure.
  Different from a breakdown, which is a set of parts beside their total.
- **`Distribution`** — a balance across the bands the server aged it into, with
  a two-pixel rule above each band that warms as the money gets older. **The
  rule is a band marker, not a measurement.** No width anywhere encodes an
  amount, because the browser would have to divide to know one.
- **`Meter`** — the only bar in the product, and it is not a chart: the fill is
  a whole-number percentage the API returned for that record, and the figure is
  printed beside it because a bar alone is not a number anybody can quote.
- **`IdentityCell`** / **`PlaceCell`** — a register row's reference with the two
  or three words that say which record it is, and where in the development it
  sits. The anchor of every register in the product.

### What is deliberately absent

No charts. No sparklines, trends, deltas, health scores, projections or
occupancy dials. Where the API returns no series, none is drawn — and none of
these modules returns one. Premium information design does not require invented
analytics, and a plausible line is worse than an empty space, because somebody
will quote it.

---

## 4. The shell

```
.app                                data-rail="auto | expanded | collapsed"
├── .sidebar                        the rail
│   ├── brand
│   ├── ProjectSwitcher             inside a project; "Projects" outside one
│   ├── nav groups                  Overview · Development · Commercial · Delivery · Finance · Governance
│   └── footer                      who you are · Settings · Sign out
├── .context-bar                    menu (phone) · rail toggle · breadcrumbs · utilities
└── .content                        PageHeader, then the section's cards
```

**The rail replaces the project-wide tab strip.** Twelve modules do not fit
in a row of tabs, and a row of tabs cannot say which ones belong together. The
groups are the developer's own departments — Development (Land, Permits,
Inventory), Commercial (Pricing, Sales & Legal, Payment Plans, Collections),
Delivery (Construction), Finance (Unit Economics), Governance (Documents,
Access) — with Overview on its own at the top. A group with nothing the reader
may open is not drawn.

Delivery is its own group rather than an entry under Finance because the people
who open it are not the people who open Unit Economics. Construction is what the
build costs the developer; unit economics is what a unit earns. Design /
Engineering can read the first and cannot read the second, and a rail that put
them under one heading would suggest one permission where there are two.

**The project switcher is first-class.** It sits under the brand, shows the
project's code, status and city, and opens a searchable menu of the projects
the reader may access. Choosing one keeps the current section, because a
Finance user comparing two projects' economics should not be sent back to
Overview each time.

**The context bar is quiet.** Breadcrumbs (`Projects / RG-01 / Inventory`),
the project's status badge and its base currency, and nothing else. The page
header underneath says where you are in words; the bar only keeps that
visible while a register scrolls.

**Three rail states.** `auto` follows the viewport: full above 75rem, icons
only between 64rem and 75rem. A person can pin it `expanded` or `collapsed`
with the toggle in the context bar; the choice is kept in `localStorage`
(`reach.rail`) and read inside a `try`, so a browser that refuses storage
still gets the automatic behaviour. Collapsed items show their label as a
tooltip (`data-label`) and keep their accessible name.

**Below 64rem the rail becomes a drawer.** The context bar grows a menu
button; the rail opens as a focus-trapped `dialog` over a scrim, closes on
Escape, on the scrim and on choosing a destination, and is mounted only while
open so it never takes the keyboard from the page behind it.

**Routing is the query string.** The frontend is a static export, so an open
project and its section travel as `/projects/?project=<id>&section=<key>` and
settings as `/settings/?section=<key>`; `projectHref` and `settingsHref` in
`components/shell/navigation.ts` are the only places those strings are built.
Every rail item is a real link, so a middle click, a bookmark and the back
button all behave.

### Visibility mirrors the server

`lib/roles.ts` holds the same sets as `app/modules/*/permissions.py` — project
writers, technical writers, financial readers, pricing writers and approvers,
internal and list price readers, sales readers, plan and collection readers,
economics readers, audit readers — and every navigation item, section, tab and
request is gated by one of them. The rule is not "hide it": it is *do not ask*.
A role that may not read Unit Economics never calls its endpoints; a role that
may not see internal prices is not offered the pricing register; a role
without the list price does not request it for the unit file's header. The
server checks everything again regardless, and a refusal it still returns is
drawn as "Not available to your role", never as a blank and never as a row of
zeros. "Withheld" and "not recorded" are different facts and must never look
the same.

---

## 5. Page anatomy

```
PageHeader        title · subtitle · actions          (compact on module screens)
Metric strip      the section's reported figures       Card > MetricGroup
DataToolbar       search · two or three filters · count · clear
Register          Card flush > TableScroll fixedFirst compact
```

Exactly one `<h1>` per screen, in the `PageHeader`. Cards use `<h2>`,
sections inside them `<h3>`, and the uppercase section heading (`SectionHeader`)
divides a card or a drawer body without adding weight.

**Registers are the product.** A register is a `Card flush` around a
`TableScroll` with the identity column pinned (`fixedFirst`) and, where rows
are many, the compact density. Cells do not wrap: a figure broken across two
lines is misread as two figures, so every cell is `white-space: nowrap` and
only a cell marked `.cell-prose` — a reason, a note — may wrap. The identity
cell is the record's reference as a `button-link` with its secondary name
underneath; that link opens the record file.

**The toolbar is one instrument.** `DataToolbar framed` draws search, the two
or three filters that narrow the register, and the count of what survived as a
single command surface. Five independently bordered boxes read as five
unrelated questions; a filter that is currently narrowing the register carries
a quiet accent so a reader who cannot find a row can see why without opening
every control.

**A register row is an object.** The identity is an `IdentityCell` inside the
link that opens the record, the row whose record is open carries an accent rail
and a tinted ground so closing the drawer lands the reader where they were, and
a chevron appears at the far right on hover. A row the server flagged — a permit
past its statutory period, one holding the programme — takes a warm rail and
nothing else: the status and flag columns already carry the words, and tinting
the whole row turns a register into an alarm panel where nothing stands out
because everything does.

**Secondary states are dots.** A `Badge` is for the state the row is about —
commercial status on Inventory, sale status on Sales. Every other state on the
same row (legal, collection, delivery, a gate) is a `StatusDot`: the same
words, a coloured dot instead of a filled tag, so a row with five states does
not read as five alarms.

**Metrics are a strip, not a grid.** `MetricGroup` is a flex row; each
`Metric` is a label over a tabular figure with an optional note, and a figure
never wraps mid-number. `size="lg"` is the one number a screen is opened for,
`md` the row it belongs to, `sm` the supporting counts. A `tone` colours the
figure only when the server said something is wrong — a loss, an overdue
balance, a breach of the margin floor.

**The project's identity is a plate, not a card.** Inside a project the Overview
opens with `ProjectPlate`: the name, who is developing it, where it is, and then
code, status, type, programme, currency and manager as inline facts. No figure
appears on it — figures are labelled and belong in the position beneath.

**Where a project is, is a place.** The location field has always been free
text, so half of them hold "Abdoun, Amman" and half hold a hundred characters of
map query string that somebody pasted because it was the fastest way to record
the site. Both are useful and neither is a name: `isUrl` decides which of the
two a screen is holding, the address goes into an `ExternalLink` labelled "Open
location", and the plate says the place.

---

## 6. The command centre

The project Overview is composed **only** from summary endpoints that already
exist — the inventory register's totals, the pricing overview and register
totals, the sales register totals, the payment plan register, the collections
summary and the unit economics summary — each requested once, and each
requested only for a role the server answers. There are no charts and no
placeholders; where a module has nothing to say yet the card says so.

**Needs attention** is a list, in lifecycle order, of the counts the server
already reports as problems: permits past their statutory period or flagged as
blocking, units needing repricing, units without a live price, reservations
needing closure, cancellations in progress, accounts overdue or disputed,
units below the margin floor or making a loss. Each row links to the section
that owns it. When nothing is flagged the card says "Nothing is flagged", which
is a finding, not an absence.

**Commercial position**, **Economic position**, **Collections** and
**Development** are metric strips over the same figures those sections show
in full. Collections is drawn per currency and never totalled across them.

Every card's request is one `Answer` (section 9): off, loading, ready,
denied, failed. A denial — the server refusing a role the browser thought
could read — draws "Not available to your role". A failure is said in words.

---

## 7. Record files

A record — a unit, a deal, a payment plan, a collections account, a permit —
opens over the register that led to it, in a `Drawer`, and keeps the register
where it was. The header is the record's identity and stays put; the body
scrolls under it.

```
Drawer
├── eyebrow            "Unit" · "Deal file" · "Payment plan" · "Collections account"
├── title              the reference
├── subtitle           what it is, where it is, who it is with
├── meta               the state badges
├── facts strip        three or four figures somebody opened it for
├── tabs               the sections
└── body               the selected section
```

**The facts strip is role-shaped.** A unit's header shows the list price, the
margin, the outstanding balance and the weighted area — but each fact is
present only for a role entitled to it, because each is fetched only for a
role entitled to it. A Sales Advisor's unit header has the list price and the
area; a Collections officer's has the outstanding balance and the area; a
Finance user's has all four.

**Unit 360** — Overview (the four status dimensions side by side, release
readiness, the price, an economics snapshot, a collections snapshot, the
commitment), Areas & features, Pricing (the live price and how it was built,
as a server-ordered waterfall with the arithmetic one click away), Sales &
legal, Collections, Economics (from revenue to profit as the server's own
waterfall, the cost composition, the unit's own costs), Release and History.
Sections a role cannot read are not offered.

**The deal file** — a lifecycle strip (Reserved · Contracted · Registered ·
Handed over, drawn from the server's statuses), then Commercial (the
reservation, the quote as a waterfall, the commercial inputs and what happens
next), Buyers, Contract (the frozen terms and taxes), Legal (the timeline and
the milestone form), Payment plan, Collections (for collection readers only),
Cancellation and Handover, each present only when the record exists.

**The payment plan** carries the contract principal, the total buyer payable,
the instalment count with its reconciliation and the effective date in its
header; the schedule editor types shares as percentages and money in the
contract's currency. **The collections account** carries outstanding,
collected, unapplied cash and the next follow-up.

**The contract file** — Position (commitment, certification and cash as three
separate compositions with their bases written above them), Lines, Variations,
Certificates, and Invoices & payments. The Position tab is the record's whole
argument: this is the screen where somebody is most tempted to treat the three
as one, so they never share a row and the reader is never invited to subtract
one from another. Retention and advance sit under cash, not under cost.

**The certificate file** carries the waterfall in the server's order — work
certified, retention withheld, retention released, advance recovered, other
deductions, tax, net due — and recomputes none of it. Applying those deductions
in a different sequence gives a different answer on the same inputs, and
`net_due` is the ceiling an invoice is approved within, so a browser-side sum
disagreeing by a cent would offer an approvable claim the server then refuses.
Its lines carry previously certified, this period and cumulative as three
columns, because a single column labelled "certified" is read as whichever one
the reader expected.

**Narrow drawers** (`narrow`) are for records with less to say — a permit.
Below 64rem every drawer takes the whole screen, and the way back is a button
at the top left, where a thumb expects it.

---

## 8. Forms

```
Form
├── FormSection        a titled group: Identity · Financial basis · Features
│   └── FieldRow       two, three or four fields side by side; one column on a phone
│       └── Field      label · control · hint · error · "optional"
└── FormActions        the primary action, and the way out
```

**Money is entered denominated.** `MoneyInput` shows the record's currency
code beside the control and keeps the exact string the person typed; nothing
is parsed into a float on the way to the server.

**Rates are entered as percentages.** `RateInput` shows `%` and the person
types `5` or `18.5`; the caller sends the server's fraction of one through
`fractionFromPercent`, which moves the decimal point by string manipulation and
never multiplies. The reverse, `percentInput`, fills the control from a stored
fraction. A factor — a weighting, a share — is not a rate and is entered as
the fraction it is.

**Edit forms are grouped.** `EditForm` takes fields with a `group`, a `width`
and an `affix`, draws one `FormSection` per group, and sends only the fields
that changed.

**Validation is the server's.** The browser sends what was typed; the message
on refusal is the server's own words, in a `Notice`. The only thing a form
decides locally is whether a required control is empty.

---

## 9. Primitives

Imported from `@/components/ui`. Each has one responsibility, and none of them
knows a business rule.

| Primitive                                   | What it is for                                                        |
| ------------------------------------------- | --------------------------------------------------------------------- |
| `PageHeader` (`compact`)                    | Where you are. One per screen.                                         |
| `SectionHeader`                             | A division inside a card or a drawer, with room for actions.           |
| `Card` / `SubPanel`                         | The one container, and a bordered region inside it.                    |
| `Tabs` / `TabPanel`                         | Sections of a place. A real tablist; arrow keys work.                  |
| `Drawer` (`facts`, `actions`, `narrow`)     | A record file opened over the register it came from.                   |
| `Button` / `ButtonRow`                      | Every action. `default`, `primary`, `danger`, `quiet`, `link`.         |
| `Field` / `FieldRow` / `FormSection`        | A control with its label; controls side by side; a titled group.       |
| `MoneyInput` / `RateInput`                  | Money with its denomination; a rate typed as a percentage.             |
| `FormActions` / `StickyActions`             | The way a form ends.                                                   |
| `DataToolbar` / `ToolbarFilter`             | The strip that narrows a register: search, filters, count, clear.      |
| `TableScroll` (`fixedFirst`, `compact`)     | A wide register that scrolls inside itself.                            |
| `KeyValueGrid` / `KeyValue`                 | Labelled facts about one record.                                       |
| `Metric` / `MetricGroup`                    | One reported number, labelled; a strip of them.                        |
| `Position` / `PositionFigure`               | The figures a page is opened for, label beneath, tear-sheet style.     |
| `PositionSupport` / `PositionSupportItem`   | The ruled line of supporting facts under a position.                   |
| `StatStrip` / `StatStripItem`               | Four or five counts in one compact band.                               |
| `Breakdown` / `BreakdownRow`                | The parts of a total, with a leader to each amount.                    |
| `Distribution` / `DistributionBand`         | A balance across the bands the server aged it into.                    |
| `Meter`                                     | A percentage the server reported, drawn at the width it reported.      |
| `IdentityCell` / `PlaceCell`                | A register row's reference and where it sits.                          |
| `ExternalLink`                              | A destination outside the product, named rather than addressed.        |
| `InlineMeta` / `InlineMetaItem`             | Small facts in a line: "Code RG-01 · Status Active".                   |
| `Waterfall` / `WaterfallRow`                | The lines a figure is made of, in the server's order, to the total.    |
| `Badge` / `StatusDot`                       | The state a row is about; every other state on the same row.           |
| `Notice`                                    | Something the system needs to say.                                     |
| `EmptyState` (`compact`) / `Loading` (shapes) | Nothing here yet; waiting, in the shape of what is coming.           |
| `Timeline` / `TimelineItem` / `Steps`       | What happened to a record, in order; the named steps it passes.        |
| `ConfirmDialog` / `PromptDialog`            | Confirm something irreversible; collect the reason an action needs.    |
| `Icon`                                      | Hand-drawn inline SVGs, one per navigation item and control.           |

`Stat`/`StatRow` remain as aliases of `Metric`/`MetricGroup`; `Panel` of
`Card`; `FilterBar` for the two forms that have not yet moved to the toolbar.

### Buttons

One `primary` per view. Everything else is `default`. In-table and in-list
actions are `small`, and `quiet` where they sit beside data they must not
outweigh. `link` is a record identifier that opens the record — it reads as
data and behaves as a link, and it is the only button that may be under 24px
tall, because it is text in a row.

`danger` is an outline, not a fill: a red-filled button in a register reads as
an alarm rather than an option.

### Status vocabulary

Status words live with the module that owns them, next to the labels:

- `components/projects/inventory/statusLabels.ts` — the four unit dimensions
- `components/projects/sales/labels.ts` — reservations, sales, gates,
  exceptions, legal events, cancellations, handovers, clearances, KYC
- `components/projects/payments/labels.ts` — versions, triggers, allocation
- `components/projects/collections/labels.ts` — receipts, instalments,
  buckets, disputes, waivers, restructures, refunds, clearance
- `components/projects/economics/labels.ts` — versions, pools, profitability
- `components/projects/construction/labels.ts` — budgets, contracts, variations,
  certificates, invoices, payments, milestones, forecasts — and the two that
  decide something rather than name it: `varianceTone` (**positive is over
  budget**) and `headroomTone` (negative is committed past the authorisation).
  Both live in one place because a second copy would eventually disagree, and
  the disagreement would print an overrun in the colour used for good news.

A status the interface has not been taught falls through unchanged and is
drawn neutral. It is still a status somebody needs to see.

A unit's four dimensions — commercial, legal, collection, delivery — are always
shown side by side and never merged. "Sold" is not one fact in this product: a
unit can be contracted, unpaid, unregistered and undelivered at the same time,
and three different teams need their own answer without reading somebody
else's as theirs.

### Numbers, money and dates

**Calculation and presentation are different things, and only one of them is
allowed here.** React performs no financial arithmetic — no totals, no tax, no
discounts, no margins, no allocations, no currency conversion, ever.
Presentation formatting is allowed, and `lib/format.ts` is the only place it
happens:

- **Money** — `money(value, code)` turns the server's exact Decimal string into
  `JOD 228,000.00`: integer digits are grouped, the sign is kept, every
  decimal digit the server sent is preserved, and the real currency code is
  prepended. The value is never passed through `Number()`, `parseFloat` or
  `Intl.NumberFormat`. No rounding, no scale change, no FX.
- **Denomination is resolved, never assumed.** Price versions, reservations,
  contracts, tax lines, plans, receipts and benchmarks each carry their own
  `currency_id`; the project workspace loads the currency register once and
  `useCurrencyCode` resolves each record's own denomination. An id the map
  cannot resolve renders the figure grouped but undenominated — never labelled
  with a guess. Amounts in different currencies are never added, and a
  collections summary is drawn per currency.
- **Rates and fractions are not money.** A stored fraction is shown as a
  percentage through `percent()`, which moves the decimal point by string
  manipulation; a factor or a share is shown as the server sent it.
- **Business dates** — `businessDate("2026-08-30")` renders `30 Aug 2026`,
  parsed as calendar components and never constructed into a JavaScript
  `Date`. Date inputs and API payloads stay ISO; only presentation changes.
- **System timestamps** are instants, not calendar dates, and are never fed
  through `businessDate`.

---

## 10. Interaction

**Records open over the register, not under it.** Escape closes, the scrim
closes, the page behind stops scrolling, and focus moves in and comes back.

**Progressive disclosure by section, not by accordion.** A record's sections
are its tabs, because the person opening one is usually one of five teams and
only needs their own. Sections that do not exist yet — a cancellation that was
never opened — are not offered; sections a role may not read are not offered.

**Reasons are collected in a labelled dialog.** `PromptDialog` says what the
reason is for and stores it beside the change.

**Overlays stack, and only the top of the stack owns the keyboard.** Drawer,
the mobile navigation, the switcher menu, `ConfirmDialog` and `PromptDialog`
all sit on one shared helper (`components/ui/overlay.ts`). A reason dialog
inside a drawer nests correctly: the first Escape closes the dialog, the
second closes the drawer, and one press never closes both.

**Confirmation is reserved for the irreversible.** Everything reversible just
happens; a dialog in front of a reversible action teaches people to dismiss
dialogs.

**Affordances mirror the server; they never replace it.** A button is hidden
when the server would refuse it. The server checks again regardless, and the
message the person sees on refusal is the server's own words.

---

## 11. Empty, loading, denied, failed

`lib/answer.ts` names the five ways one request answers a screen — `off`
(never asked, because the role could not be answered or the record has
nothing to ask about), `loading`, `ready`, `denied`, `failed` — and
`useAnswer(enabled, load, deps)` asks once, only when enabled. Every card on
the command centre and every role-shaped section of a record file is one
`Answer`.

`EmptyState` names what is missing and what to do about it — never a
placeholder figure or an invented row. `compact` is for an empty section
inside a record, where a full-height empty state would shout.

`Loading` takes a label and a `shape` — `metrics`, `rows` or `page` — so the
skeleton is the shape of what is coming and the page does not jump when it
arrives.

`Notice` has four tones. `error` is announced to assistive technology; the
others are polite status updates. Error text is the server's message wherever
there is one.

---

## 12. Responsive behaviour

| Width         | Behaviour                                                                        |
| ------------- | -------------------------------------------------------------------------------- |
| ≥ 75rem (1200)| Full rail with labels. Twelve-column page grid. Drawers at `--drawer-width`.      |
| 64–75rem      | Rail collapses to icons (`auto`); labels become tooltips. Grids drop a column.    |
| < 64rem (1024)| Rail becomes a drawer behind a menu button. Record drawers take the full width.   |
| < 48rem (768) | Single-column forms and key/value grids; metric strips and facts wrap.            |
| < 34rem (544) | The brand keeps its mark; tabs scroll sideways; the page header stacks.           |

Registers are wide because the data is wide. They scroll sideways inside
`TableScroll`, with the identity column pinned. **The page body itself never
scrolls sideways at any width**; the browser walkthrough asserts this on every
screen at 1600, 1440, 1280, 1024, 768 and 390 wide.

---

## 13. Accessibility

- One `<h1>` per screen; headings descend without skipping.
- The rail is a `<nav>` with a label; the current item carries
  `aria-current="page"`; the breadcrumbs are a `<nav aria-label="Breadcrumb">`
  around an ordered list; the collapsed rail keeps every item's accessible
  name.
- Tabs are a real `tablist`: ArrowLeft/ArrowRight move both selection and
  focus, Home and End jump to the ends, `aria-selected` and roving `tabIndex`
  stay in step, ids are namespaced per group, and the selected tab is scrolled
  into view when the row overflows.
- Drawers, the mobile navigation, the switcher menu and dialogs are
  `role="dialog"`/`alertdialog` with `aria-modal` and an accessible name, on
  the shared overlay helper: focus moves in on open, Tab and Shift+Tab are
  contained inside the topmost overlay, Escape closes the topmost overlay
  only, and on close focus returns to the control that opened it.
- Every table has a `<caption>` (visually hidden) and `scope`d headers;
  `TableScroll` is focusable so a keyboard can scroll it.
- Every control is at least 24px tall; the rail's items and the context bar's
  buttons are 40px.
- Focus is always visible: a 2px accent ring on the light surface, a light
  ring on the dark rail.
- Text and its background meet WCAG AA on every token pair used together:
  the rail's text on `--nav-bg`, the muted text on `--surface-secondary`,
  every intent's solid colour on its soft fill.
- Colour is never the only carrier of meaning.
- `prefers-reduced-motion` removes all transitions and animation.

---

## 14. What this system deliberately does not have

No component library (MUI, Ant, Chakra, Mantine, shadcn, Radix, Headless UI).
No CSS framework (Tailwind, Bootstrap). No CSS-in-JS. No icon package — the
`Icon` primitive is a map of hand-drawn paths. No chart library, and no
charts: a bar drawn from server counts would be the first step towards a bar
drawn from nothing. No table, form, date or animation library. No client
state library (Redux, Zustand, React Query). Data is fetched in the component
that shows it, through `lib/api`, and held in `useState`. No dark theme. No
FX. No construction screens before PR-MVP-09 exists to record what they would
show.

The frontend is a **static export** (`output: "export"`, `trailingSlash:
true`) served by FastAPI from `frontend/out`. There are no server components,
no server actions, no SSR and no dynamic route segments.

Adding any of the above is a decision with a cost, and it should be argued for
in a pull request of its own rather than arriving as a transitive dependency of
a button.

---

## 15. Extending it

1. Compose from the primitives first. Most "new components" are a `Card` with a
   `SectionHeader`, a `MetricGroup` and a `TableScroll`.
2. If a genuinely new primitive is needed, add it to `components/ui/`, export it
   from `components/ui/index.ts`, and give it exactly one responsibility.
3. Style it with the tokens in section 3. If a token is missing, add it to
   `:root` — never a literal colour, radius or duration in a rule.
4. Keep business rules out of it. A primitive that knows what a price is, or who
   may approve one, is a primitive in the wrong place.
5. Gate by role before you fetch. A new module gets a set in `lib/roles.ts`
   that mirrors its `permissions.py`, a `visible` rule on its navigation item,
   and `useAnswer` around every request a role might be refused.
6. Never total, convert or derive a figure in the browser. If the screen needs
   a number the API does not return, the API grows the number.
7. Run the checks: `npm run lint`, `npx tsc --noEmit`, `npm run build`, and the
   browser walkthrough — every role, six widths, every drawer — reading the
   console and the overflow report before calling anything done.
