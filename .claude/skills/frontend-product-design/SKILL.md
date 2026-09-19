---
name: frontend-product-design
description: Decide what a Reach screen should say and how it is composed — information hierarchy, which figure leads, which surface holds it, what belongs behind a disclosure. Use when designing or redesigning a page, workspace, card, register, record header or analysis section, or when a request sounds like "this looks bad", "revamp this", "make it modern" or "the part below needs work".
---

# Designing a screen in Reach

Reach is a real-estate development operating system. A screen earns its place by
helping a developer answer one question — *am I selling?*, *where is the project
overall?*, *what is overdue?* — before anyone inspects a record. Decoration that
does not move that answer forward is cost, not polish.

The visual rules already exist and are **not yours to reinvent**. This skill is
how to *think*; `docs/UX_SYSTEM.md` is what is *true*.

## Read before you design

| Source | What it owns |
| --- | --- |
| `docs/UX_SYSTEM.md` | The design system itself: composition (§1), tokens (§2), type scale (§3), shell (§4), the primitive table (§5), registers (§6), records and forms (§7), what each workspace leads with (§8), financial boundaries (§9), accessibility and responsive acceptance (§10) |
| `docs/UX_PAGE_AUDIT.md` | Full pages, never side drawers — including on mobile |
| `frontend/src/app/globals.css` | The single `:root` block. Every literal colour and spacing value lives here |
| `frontend/src/components/ui/index.ts` | The complete primitive vocabulary you are composing from |
| `docs/UX_MVP_FINISH_2026_09_11.md`, `docs/UX_ROADMAP_2026_09_10.md`, `docs/UX_AUDIT_2026_09.md` | Open visual debt and what has already been decided |

Read §8 for the specific workspace you are touching **before** proposing a
layout. Project Overview, Portfolio, Project Analysis, Sales, Collections,
Construction and Cashflow each have a stated lead. Changing what a page leads
with is a product decision, not a styling decision.

## The method

**1. Name the question the screen answers.** One sentence, in the owner's words.
If you cannot write it, you are decorating, not designing.

**2. Choose the hierarchy before the containers.** `docs/UX_SYSTEM.md` §1 gives
the order: identify the development or asset → lead with the server-reported
figure that supports the decision → show exceptions and the action that opens
the owning workflow → keep registers compact → put basis, history and secondary
evidence behind labelled disclosures.

**3. Give each surface one job.** One lead figure per card, on its stage. The
figures beside it are a ledger, not four more heroes. Use the open band for
counts, white for working records, quiet inset surfaces for supporting evidence.
A supporting section does not need a card around it.

**4. Pick the primitive that already owns the responsibility.** Go through the
table in §5 and name the one you are using. If nothing fits, extend the
canonical component — do not invent `CardV4`, a second stylesheet layer, or a
screen-local copy.

**5. Say what the data is actually doing.** Loading, absent, denied, failed,
partial and zero are six different things and look different. See the
`financial-ui-integrity` skill.

**6. Draw it at 390px in your head before 1440px.** The narrow width is where
a composition with four peers and a hero fails. §10 lists the widths that must
be validated.

## Anti-patterns this repository has actually shipped

These are real. They were merged, seen by the owner, and corrected.

- **Four hero figures in a row.** `docs/UX_SYSTEM.md` §3 names it: *"Four hero
  figures in a row is a card with no lead."* If every figure is `--metric-hero`,
  nothing is.
- **A raw key/value dump called a redesign.** A department section that printed
  every returned field at equal weight, with a hairline added, was described as
  a revamp. It was not. If the change is only a border and spacing, say so and
  do the composition work.
- **Two cards competing for the same money.** The selling band and the
  Collections card both printing contracted value. §8 states the selling band
  does not repeat the money the Collections card owns. Ask which surface *owns*
  a figure before showing it twice.
- **An amber amount.** Colour on a figure is reserved for danger. A warning is a
  mark beside the label, never a tinted number — the warning and danger text
  tones are one colour to a deuteranope.
- **A chart because the section looked empty.** Financial series need an owning
  API's comparable source series and safe normalised geometry first (§9). An
  invented ratio, a fabricated trend or an animated counter is a product
  falsehood, not a visual improvement.
- **Three variants of the same control.** Tabs once had `workspace`, `record`
  and `analysis` variants; one shipped unstyled because nothing checked it.
  Variants multiply the surfaces where drift hides.

## Deciding, when the owner has not

Design questions that change what the business reads are the owner's. Ask, do
not assume, when the answer changes which figure leads, which population a count
is drawn from, or whether two things may be combined. Ask in the owner's
vocabulary — units, buyers, instalments, receipts — not in component names.

Everything else — spacing, which primitive, where the disclosure sits, how it
reflows at 768px — is yours. Make the call and state it.

## Evidence before you call a design done

A structural test proving a component is *shaped* right does not prove the
screen *reads* right. `docs/UX_SYSTEM.md` §10 is explicit: the source guards
"do not substitute for visual or keyboard review."

Required before claiming a visual change:

- The screen rendered at 1440px and 390px with real loaded data, not an empty
  fixture and not production data.
- Comparable before/after crops of the same region.
- Named remaining visual debt. A partial improvement described honestly is
  worth more than a complete one described optimistically.

State plainly what you did not look at.
