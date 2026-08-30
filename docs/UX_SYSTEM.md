# UX System — Reach Developments Station

The product's design system: one light theme, one token layer, and a small set
of hand-written primitives. No component library, no icon package, no CSS
framework, no chart library, no client state library.

Everything here lives in two places:

| What                | Where                              |
| ------------------- | ---------------------------------- |
| Tokens and classes  | `frontend/src/app/globals.css`     |
| Primitives          | `frontend/src/components/ui/`      |
| Application chrome  | `frontend/src/components/AppShell.tsx` |

If a screen needs something this document does not describe, the answer is
almost always a new composition of what is here — not a new dependency.

---

## 1. What this product is, and what that means for its interface

This is the record of what a real estate developer owns, what it is selling,
what it has agreed, and what it is owed. People use it to answer questions they
will later have to defend: to a board, to a lender, to a buyer's lawyer, to an
auditor.

Three consequences run through every decision below.

**Nothing on screen may be invented.** Every figure, status, blocker, gate and
total is a value the API returned on that request. The browser lays out and
labels; it never calculates a price, a discount, a tax, a margin, a total, a
release eligibility, or an approval requirement. There is exactly one
implementation of each of those, and it is on the server. A second one in
React would eventually disagree with it, and the disagreement would be
discovered by somebody signing a contract.

**Empty space beats a plausible number.** There are no placeholder cards, no
sample series, no "0%" standing in for "not measured". Where a total cannot
honestly be produced — a project whose contracts are in two currencies — the
screen says so and shows nothing.

**A word carries the meaning; colour only repeats it.** Nothing on any screen
is understood by hue alone. Status is always written out, and the badge behind
it is a skim aid.

---

## 2. Theme

**Light only.** `html { color-scheme: light; }`, and there is no
`prefers-color-scheme` rule anywhere in the stylesheet.

This is deliberate rather than unfinished. The screens here get printed,
screenshotted into board packs and shared as evidence, and a document that
looks different on the reviewer's machine than on the preparer's is a document
somebody has to explain. A dark theme is a real piece of work — every token, every
status colour, every contrast pair — and half of one is worse than none.

If a dark theme is ever added, the token layer is where it goes: redefine the
tokens in section 3 under both `@media (prefers-color-scheme: dark)` and an
explicit `[data-theme="dark"]`, and change nothing else.

---

## 3. Tokens

All tokens are CSS custom properties on `:root`. Components never hard-code a
colour, a radius, a spacing step or a duration.

### Surfaces

| Token             | Value     | Use                                              |
| ----------------- | --------- | ------------------------------------------------ |
| `--canvas`        | `#f4f6f8` | The page behind everything.                      |
| `--surface`       | `#ffffff` | Cards, the application bar, drawers, dialogs.    |
| `--surface-sunken`| `#f7f9fb` | Forms, filter strips, nested regions.            |
| `--surface-hover` | `#f2f5f8` | Row and control hover.                           |
| `--border-subtle` | `#e3e7ec` | Dividing one thing from the next.                |
| `--border-strong` | `#c6ced8` | The edge of something you can type in or press.  |

### Text

| Token              | Value     | Use                                        |
| ------------------ | --------- | ------------------------------------------ |
| `--text-primary`   | `#10141b` | The answer.                                |
| `--text-secondary` | `#4d5867` | Supporting prose, field labels.            |
| `--text-muted`     | `#78828f` | Column headers, term labels, footnotes.    |
| `--text-inverse`   | `#ffffff` | On a filled accent.                        |

### Intent

Each intent has a solid colour for text and a soft one for a fill.

| Intent    | Solid     | Soft      | Means                                              |
| --------- | --------- | --------- | -------------------------------------------------- |
| `accent`  | `#17527d` | `#e8f0f7` | The product's one action colour. Also `info`.       |
| `success` | `#146c43` | `#e5f3ec` | Done, given, cleared, available, approved.          |
| `warning` | `#8a5300` | `#fbf0dd` | Waiting on somebody, held, past due but not failed. |
| `danger`  | `#a02015` | `#fbeae8` | Refused, expired, cancelled, blocked.               |

`--accent-hover` (`#113f61`) is the pressed and hovered accent.

### Spacing, radius, elevation

`--space-1` … `--space-8` = `0.25 / 0.5 / 0.75 / 1 / 1.5 / 2 / 3 / 4 rem`.

`--radius-control: 6px` for anything you type in or press, `--radius-card:
10px` for a container, `--radius-pill: 999px` for a badge or chip.

`--shadow-xs` for a card at rest, `--shadow-sm` for a raised block,
`--shadow-md` for a drawer or dialog. Elevation is nearly flat on purpose: the
hierarchy comes from spacing and rules, not from stacked shadows.

### Typography

Two families: `--font-sans` (the system stack) for prose and
`--font-mono` for anything a person compares down a column — a figure, a date, a
unit reference, a contract number.

Scale, in rem: `--text-2xs` `.6875` · `--text-xs` `.75` · `--text-sm` `.8125` ·
`--text-base` `.875` · `--text-md` `.9375` · `--text-lg` `1.0625` · `--text-xl`
`1.25` · `--text-2xl` `1.5` · `--text-3xl` `1.875`.

Body text is `--text-base` (14px). This is a register-heavy product used at a
desk; a 16px body would push a fourteen-column register off the screen.

### Layout and motion

`--content-narrow: 26rem` (sign-in), `--content-standard: 78rem` (portfolio
screens), `--content-wide: 96rem` (a project workspace, which is all registers).

`--motion-fast: 120ms` for hover and colour, `--motion-base: 160ms` for
anything larger, `--ease` for both. Nothing animates position or size;
`prefers-reduced-motion` reduces everything to nothing.

---

## 4. Layout

```
AppShell
├── .app-bar          sticky: brand · Projects/Settings · who you are · sign out
└── .app-body         --content-standard, or --content-wide inside a project
    ├── PageHeader    eyebrow · h1 · subtitle · actions · meta chips
    ├── Tabs          the sections of this place
    └── TabPanel      a `.stack` of Cards
```

The bar is sticky because the registers underneath it are long, and losing
which project you are inside halfway down a thousand units is how somebody
records a reservation against the wrong development.

Exactly one `<h1>` per screen, in the `PageHeader`. Cards use `<h2>`, sections
inside them `<h3>`.

Below `34rem` the bar drops the signed-in person's name and roles and keeps the
brand, the two destinations and the way out. Below `40rem` it drops
"Developments Station" from the brand.

---

## 5. Primitives

Imported from `@/components/ui`. Each has one responsibility, and none of them
knows a business rule.

| Primitive                        | What it is for                                                       |
| -------------------------------- | -------------------------------------------------------------------- |
| `PageHeader`                     | Where you are. One per screen.                                        |
| `SectionHeader`                  | A division inside a card, with room for one action.                   |
| `Card` (alias `Panel`)           | The one container. Title, description, actions, body.                 |
| `SubPanel`                       | A bordered region inside a card: a form that opened.                  |
| `Tabs` / `TabPanel`              | Sections of a place. A real tablist; arrow keys work.                 |
| `Drawer`                         | A record opened over the register it came from.                       |
| `Button` / `ButtonRow`           | Every action. `default`, `primary`, `danger`, `quiet`, `link`.        |
| `Field` / `FilterBar` / `FormActions` / `StickyActions` | Forms, and the strip that narrows a register.  |
| `TableScroll`                    | A wide register that scrolls inside itself.                           |
| `KeyValueGrid` / `KeyValue`      | Labelled facts about one record.                                      |
| `Stat` / `StatRow`               | One reported number, labelled.                                        |
| `Badge`                          | A short piece of state, coloured by what it means.                    |
| `Notice`                         | Something the system needs to say.                                    |
| `EmptyState` / `Loading`         | Nothing here yet; waiting.                                            |
| `Timeline` / `TimelineItem`      | What happened to a record, in order.                                  |
| `Steps`                          | The named steps a record passes.                                      |
| `ConfirmDialog` / `PromptDialog` | Confirm something irreversible; collect the reason an action needs.    |
| `Icon`                           | Six inline SVGs. There is no icon package.                            |

### Buttons

One `primary` per view. Everything else is `default`. In-table and in-list
actions are `small`. `quiet` is for an action that sits beside data it must not
outweigh. `link` is a record identifier that opens the record — it reads as
data and behaves as a link, and it is the only button that may be under 24px
tall, because it is text in a row.

`danger` is an outline, not a fill: a red-filled button in a register reads as
an alarm rather than an option.

### Badges and status

Status vocabulary lives with the module that owns it, next to the labels:

- `components/projects/inventory/statusLabels.ts` — `statusLabel`, `statusTone`
- `components/projects/sales/labels.ts` — `reservationLabel`/`Tone`,
  `saleLabel`/`Tone`, `gateLabel`/`Tone`, `handoverLabel`/`Tone`, and the rest

A status the interface has not been taught falls through unchanged and is drawn
neutral. It is still a status somebody needs to see.

A unit's four dimensions — commercial, legal, collection, delivery — are always
shown side by side and never merged. "Sold" is not one fact in this product: a
unit can be contracted, unpaid, unregistered and undelivered at the same time,
and three different teams need their own answer without reading somebody
else's as theirs.

### Numbers and money

Any figure a person compares down a column gets `.num` in a table (monospace,
tabular figures, right-aligned, never wrapped) or `mono` on a `KeyValue`. A
`Stat` is already monospaced and tabular.

Currency codes are shown where the API gives them. Nothing is reformatted,
rounded or localised in the browser: the server sends a decimal string and that
string is what appears, because a rounded figure on a contract screen is a
wrong figure.

---

## 6. Interaction

**Records open over the register, not under it.** `Drawer` gives a record the
full height of the screen and leaves the list in place behind it. Escape
closes, the scrim closes, the page behind stops scrolling, and focus moves in.
Unit 360 and the deal file both use it.

**Progressive disclosure by section, not by accordion.** Unit 360 has six
sections and the deal file has five, because the person opening one is usually
one of five teams and only needs their own. Sections that do not exist yet — a
cancellation that was never opened — are not offered.

**Reasons are collected in a labelled dialog.** `PromptDialog` replaced
`window.prompt`, which could not be labelled, could not say what the reason was
for, and is silently disabled in several embedded browsers — which turns a
refused clearance into a button that appears to do nothing.

**Confirmation is reserved for the irreversible.** `ConfirmDialog` guards
things that cannot be undone from the interface. Everything reversible just
happens; a dialog in front of a reversible action teaches people to dismiss
dialogs.

**Affordances mirror the server; they never replace it.** A button is hidden
when the server would refuse it, because offering an action that always fails
is worse than offering none. The server checks again regardless of which button
was on screen, and the message the user sees on refusal is the server's own
words.

---

## 7. Empty, loading and error

`EmptyState` names what is missing and what to do about it — never a
placeholder figure or an invented row.

`Loading` takes a label; with `lines` it draws a skeleton the shape of what is
coming, so the page does not jump when it arrives.

`Notice` has four tones. `error` is announced to assistive technology; the
others are polite status updates. Error text is the server's message wherever
there is one, because the server is the only thing that knows why it refused.

A section a role may not read says so — "Not available to your role" — rather
than rendering blank. "Withheld" and "not recorded" are different facts and
must never look the same.

---

## 8. Responsive behaviour

| Width    | Behaviour                                                              |
| -------- | ---------------------------------------------------------------------- |
| 1440     | Full layout. Key/value grids at three columns.                          |
| 1280     | The same. Registers begin to scroll inside themselves.                  |
| 1024     | Grids drop to two columns; drawers take the full width.                 |
| 768      | Single-column forms; tab rows scroll sideways.                          |
| 390      | The bar keeps brand, destinations and sign out. Stats wrap to two.      |

Registers are wide because the data is wide — a unit has four status dimensions
and a deal has five records behind it. They scroll sideways inside
`TableScroll`, with the identifier column pinned where it helps. **The page
body itself never scrolls sideways at any width**; the browser walkthrough
asserts this on every screen at all five widths.

---

## 9. Accessibility

- One `<h1>` per screen; headings descend without skipping.
- Tabs are a real `tablist`: arrow keys move, `aria-selected` is set, each panel
  is labelled by its tab. Ids are namespaced per tab group, so a drawer's
  sections over a project's sections do not collide.
- Drawers and dialogs are `role="dialog"`/`alertdialog` with `aria-modal`, an
  accessible name, focus moved in on open and Escape to close.
- Every table has a `<caption>` (visually hidden) and `scope`d headers.
- `TableScroll` is focusable so a keyboard can scroll it.
- Controls a finger has to hit are at least 24px tall; the walkthrough asserts
  this at 390px.
- Focus is always visible: a 2px accent outline, offset, on every focusable
  thing.
- Colour is never the only carrier of meaning.
- `prefers-reduced-motion` removes all transitions and animation.

---

## 10. What this system deliberately does not have

No component library (MUI, Ant, Chakra, Mantine, shadcn, Radix, Headless UI).
No CSS framework (Tailwind, Bootstrap). No CSS-in-JS. No icon package. No chart
library. No table, form or animation library. No client state library (Redux,
Zustand, React Query). Data is fetched in the component that shows it, through
`lib/api`, and held in `useState`.

The frontend is a **static export** (`output: "export"`, `trailingSlash: true`)
served by FastAPI from `frontend/out`. There are no server components, no server
actions, no SSR and no dynamic route segments — an open project travels in the
query string, because project identifiers are runtime data and a dynamic
segment would need them at build time.

Adding any of the above is a decision with a cost, and it should be argued for
in a pull request of its own rather than arriving as a transitive dependency of
a button.

---

## 11. Extending it

1. Compose from the primitives first. Most "new components" are a `Card` with a
   `SectionHeader` and a `KeyValueGrid`.
2. If a genuinely new primitive is needed, add it to `components/ui/`, export it
   from `components/ui/index.ts`, and give it exactly one responsibility.
3. Style it with the tokens in section 3. If a token is missing, add it to
   `:root` — never a literal colour, radius or duration in a rule.
4. Keep business rules out of it. A primitive that knows what a price is, or who
   may approve one, is a primitive in the wrong place.
5. Run the checks: `npx tsc --noEmit`, `npx eslint .`, `npx next build`, and the
   browser walkthrough across the five widths.
