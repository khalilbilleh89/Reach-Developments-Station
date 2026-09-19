---
name: frontend-review
description: Review a Reach frontend change — your own before pushing, or someone else's diff, PR or review comment. Use when asked to review, critique, check or sanity-check frontend work, when CI guards fail, or before declaring a UI change complete.
---

# Reviewing a frontend change

Reviewing here is not style commentary. It is asking whether the screen tells
the truth, whether it says the same thing as every other screen, and whether the
evidence offered actually supports the claim being made.

## Read before you review

| Source | What it settles |
| --- | --- |
| `docs/UX_SYSTEM.md` §5, §8, §9, §10 | Which primitive owns this, what the workspace leads with, the financial boundary, the accessibility and responsive acceptance list |
| `docs/ENGINEERING_RULES.md` §5, §11, §12 | Frontend rules, PR discipline, the definition of done |
| `docs/UX_PAGE_AUDIT.md` | Full pages, retained register state, Back, dirty-form confirmation |
| `docs/DELETION_POLICY.md`, `docs/DELETION_AUDIT.md` | Whether a new creation flow left a removal gap |
| `tests/test_product_experience.py` | The structural guards and what each one actually proves |

## Read in this order

**1. What does the diff claim?** Compare the PR body against the diff. "Revamp"
must be a composition change; a hairline and some padding is not one. An
overstated change is a defect — it makes the next reviewer trust the next claim.

**2. Does any figure change meaning?** Any new or moved number: where does it
come from, who owns it, is it already shown elsewhere on the page, and is it
denominated by the record's own currency? See `financial-ui-integrity`.

**3. Are all the answers drawn?** For each read: `off`, `loading`, `ready`,
`denied`, `failed` — plus absent, partial and zero within `ready`. A failure
rendered as zeros or as a cheerful empty state is the most damaging bug this
interface can have, because it looks correct.

**4. Is the request gated before it is made?** A role that may not read a module
must not fetch it. Hiding a rendered field is not permission enforcement.

**5. Does it use the canonical primitive?** A second name, a local copy, a new
`variant`, a hex colour outside the `:root` block, or a second stylesheet layer
is drift. Two screens then diverge while both believe they are canonical.

**6. Does it survive 390px?** And 768px, 1024px, 1280px, 1440px, 1600px. Long
amounts must not clip or overlap. `docs/UX_SYSTEM.md` §10 is the list.

**7. Did anything that creates a record forget to delete it?**

**8. Is the evidence real?** See below.

## Judging evidence

**A test that agrees with you is not evidence.** The structural guards in
`tests/test_product_experience.py` prove a component is *shaped* right — the
right import, the right class, no forbidden token. They cannot prove it *works*.
`docs/UX_PAGE_AUDIT.md` says it plainly of its own suite: source checks
complement browser checks; they do not prove every business workflow.

When reviewing a claim, ask:

- **Does the fixture have production's shape?** A UUID field fed a currency code
  in a fixture let a raw UUID reach a live page with a green suite behind it.
- **Would this guard fail on the code before the fix?** If you cannot show it
  failing, it proves nothing. Check out the parent commit and run it.
- **Does the assertion match the intent, or the text?** A scan for a word can
  match the comment explaining the word's removal. Precision, not breadth.
- **Was the screen actually loaded?** With real data, settled layout, the
  production export — not an empty fixture, never production data.
- **What was not checked?** A review that lists nothing unverified has not
  looked hard enough.

## Writing the review

State the problem, the consequence, and the smallest correct fix. Separate:

- **Blocking** — wrong figure, undenominated money, browser arithmetic, a
  failure drawn as data, an ungated request, a missing deletion path, a new
  primitive alias, a broken keyboard or focus contract.
- **Non-blocking** — composition you would have done differently, naming,
  spacing. Say which it is; do not let a preference read as a defect.

If a change is right but its stated evidence does not support it, say that
separately from the change itself. Both are real findings.

## Reviewing your own work before pushing

The same list, plus: run every check in the `frontend-implementation` skill —
including `ruff check .` and `ruff format --check .` when the diff touches any
`.py` file. Reproduce the original failure before claiming a CI fix. Read your
own diff adversarially and ask what would make CI reject it. One validated push
beats three speculative ones, and this repository's owner does not re-run CI
casually.

Open as **Draft**, stop for independent review, and never merge — a human
merges.
