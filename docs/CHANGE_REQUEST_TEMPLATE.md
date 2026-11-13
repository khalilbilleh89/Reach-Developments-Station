# Change request template (owner → GPT → Codex → pull request)

Use this whenever you want Reach to **add**, **change** or **remove** something.
It is written for this chain:

1. **You** (owner or delegate) fill in Part A in plain business language.
2. **GPT** receives the whole block, checks it, asks you what is unclear, and
   writes one Codex task per pull request (Part B tells it how).
3. **Codex** builds the change and opens the pull request under the standing
   rules in Part C, which GPT copies into every task unchanged.
4. **You** review the pull request with the checklist in Part D, then merge.

Copy everything inside the fence below into GPT, filling in Part A only.
Parts B and C stay as they are. They point at the repository's rules
([AGENTS.md](../AGENTS.md), [ENGINEERING_RULES.md](ENGINEERING_RULES.md),
[DELETION_POLICY.md](DELETION_POLICY.md), [UX_SYSTEM.md](UX_SYSTEM.md),
[design-system/README.md](design-system/README.md)) and add the habits that keep
pull requests mergeable the first time. Each rule in Part C exists because a
real pull request failed without it.

---

```text
---------------------------------------------------------------------
PART A — THE REQUEST (fill in; plain business words, no code)
---------------------------------------------------------------------

REQUEST TYPE: Add | Change | Remove | Fix          (pick one)
ONE OUTCOME:  Write the single result you want. If you wrote "and" between
              two unrelated results, make two requests.

1. WHERE
   Module / screen:   (e.g. Development > Company, Development > Land > parcel)
   Record or section: (e.g. the bank account block, the Site & utilities tab)

2. WHAT I WANT
   One or two sentences, in business words:
   (e.g. "Record each company's authorised signatories and their ID expiry.")
   Why (the business reason, one line):

3. THE QUESTION THIS SCREEN SHOULD ANSWER
   What I need to know at a glance when I open it:
   What should lead / be most visible:
   What can sit behind a click:

4. DATA
   For each field to add / change / remove:
     name · required or optional · type: text / date / money (which currency) /
     percentage / quantity (which unit) / file (PDF, max size) / Drive link /
     choice (list every choice, in order)
   Existing data that must be kept or converted, and how:
   Anything the system must calculate (state the rule; the server calculates):

5. NAMES AND WORDING  (for renames and new labels)
   Old wording → new wording:
   Where it must change: menu · breadcrumb · page title · buttons · empty and
   error messages · exports/PDFs · everywhere   (pick; "everywhere" is the default)

6. WHO
   Who can see it:
   Who can add / edit:
   Who can delete:

7. DELETE / REMOVE BEHAVIOUR
   Add: how Delete works, what blocks it (linked records), reason required?
   Remove: hide it, retire it but keep history, or delete it?
   History or evidence that must be kept:

8. MUST NOT CHANGE
   (e.g. "Bank accounts and company documents stay as they are.")

9. DONE WHEN  (the checks I will do myself, with made-up example data)
   1.
   2.
   3.

10. REFERENCE (optional)
   A similar Reach screen to copy, a sketch, or an example document.
   Never paste real customer, buyer or company data — describe it or make up
   an example.

11. PRIORITY AND TIMING (optional)
   Urgent / normal / when convenient. Any other open request this depends on:

---------------------------------------------------------------------
PART B — INSTRUCTIONS FOR GPT (do not edit)
---------------------------------------------------------------------

You turn Part A into Codex tasks. You do not write code yourself.

1. Check Part A first. If anything in sections 2, 4, 5, 6, 7 or 9 is missing,
   ambiguous or contradictory, ask the requester short numbered questions and
   wait. Never invent fields, choices, permissions or calculation rules.
2. One Codex task = one pull request = one outcome. Split the request when it
   has independent outcomes, touches more than one business domain, or would
   need more than about 20 files or 800 added lines. Say which task goes first
   when one depends on another.
3. Keep the requester's words for labels, choices and messages exactly
   (sentence case). Do not "improve" them.
4. Remove any real personal, customer or company data from what you pass on;
   replace it with clearly made-up examples.
5. Write each Codex task with these headings, in this order:
     TITLE            — imperative, specific, under 70 characters
                        (e.g. "Add authorised signatories to company records")
     GOAL             — the outcome and the business reason, two sentences
     WHERE            — module, screen, section
     REQUIREMENTS     — numbered, testable, one behaviour each
     DATA AND RULES   — fields with type/required/choices; preserved data;
                        server-side calculations; whether a migration is needed
     WORDING          — exact labels, and every place a renamed term must change
     PERMISSIONS      — see / add-edit / delete
     DELETION         — the delete or retirement behaviour and retained history
     MUST NOT CHANGE  — from section 8
     ACCEPTANCE TESTS — section 9 rewritten as numbered checks Codex must run
                        with synthetic data and report one by one
     OUT OF SCOPE     — what this task deliberately does not do
     OPEN QUESTIONS   — anything still unresolved (should normally be empty)
   Then paste PART C below, unchanged, as the last section of every task.
6. After Codex reports back, compare its report against ACCEPTANCE TESTS and
   MUST NOT CHANGE. Tell the requester plainly what is done, what is not, and
   anything Codex flagged (visual debt, skipped checks, open questions).

---------------------------------------------------------------------
PART C — STANDING INSTRUCTIONS FOR CODEX (do not edit)
---------------------------------------------------------------------

Before writing code
- Follow CLAUDE.md and AGENTS.md. Read docs/ENGINEERING_RULES.md and
  docs/DELETION_POLICY.md. For screen work open the .claude/skills listed in
  AGENTS.md (frontend-product-design, frontend-implementation, frontend-review;
  financial-ui-integrity for any amount, rate, percentage, quantity or date),
  the matching section of docs/UX_SYSTEM.md and the component entry in
  docs/design-system/README.md.
- Start a new branch from the latest origin/main. One task, one branch, one PR.
- List the open pull requests. If one changes the same files or also adds a
  database migration, say so in the PR's Review focus.
- Find the nearest existing Reach screen that does the same job and match it.
  If a requirement conflicts with a repository rule, stop and ask.

While building
- Compose only from @/components/ui primitives and approved catalogue entries.
  No new colours, no screen-local component copies, no side drawers.
- Lead with the answer to the screen's question. Show entered values at full
  weight; say what is missing once, in muted text.
- Sentence-case labels. One primary (gold) action per view. Secondary row
  actions in the row menu (⋯). Short fixed choices: segmented controls or
  choice cards; growing lists: dropdowns. Long forms (3+ sections): section
  links and the sticky save bar. Check long option labels still fit at 1440px
  and 390px.
- Loading, empty, denied and failed are four different states. The browser
  never calculates money; the server does.
- Every Add ships with a working, reasoned, audited Delete, and
  docs/deletion_contracts.json is updated.
- Renames: change every user-visible place listed under WORDING (menu,
  breadcrumb, page title, buttons, messages, tests). If you leave one on
  purpose, name it in the PR.
- Use only synthetic data in code, tests, fixtures, screenshots and the PR text.
  Never name or use production records.

Database migrations (only when the task needs one)
- Fetch origin/main immediately before creating it. Its number is the current
  Alembic head + 1, and down_revision is that head. If another migration merges
  first, renumber yours and update every reference.
- In the same PR:
    tests/test_migrations.py      HEAD_REVISION = "<your revision>"
    scripts/ci_backend_tests.py   add the revision stem to its owning domain
    scripts/ci_backend_smoke.py   add "<file>.py": ("<domain>", ("<owner test>",))
- Write a migration test that downgrades to its own parent, upgrades to "head",
  runs alembic check and proves existing data survived. Never hard-code a later
  revision in a test; read the head from ScriptDirectory.
- The downgrade either restores the old shape or refuses with a clear message
  while new data exists. Never silently drop data.

Tests and checks (run them; never claim a check you did not run)
- Never skip, delete, weaken or quarantine a test to get green. Do not add
  dependencies or ci:full to get green.
- Add or extend tests for every numbered requirement and acceptance test.
- Frontend changed: cd frontend && npm test && npx tsc --noEmit && npx eslint
  && npx next build; then pytest tests/test_product_experience.py
  tests/test_static_frontend.py (PostgreSQL).
- Python changed: ruff check, ruff format --check, and pytest for the changed
  module tests (PostgreSQL 16; never SQLite).
- Migration added: pytest tests/test_migrations.py and the migration test.
- Run python scripts/agent_preflight.py.
- Render each changed screen with synthetic data at 1440px and 390px, run
  every ACCEPTANCE TEST, and name any visual debt left.

Pull request description (PR Quality fails on any deviation)
- Fill every section of .github/pull_request_template.md. Keep the headings.
- CI phase: tick exactly one box, matching the PR's real state.
- Contract Impact and Migration Impact: each line is exactly "Yes" or "No",
  optionally followed on the same line by " — reason". Not "Guarded",
  "Partly" or "No on upgrade". Put any explanation ABOVE the fenced block,
  never below it (text below is read as part of the last answer).
- Validation results: keep the fenced block with exactly these five labelled
  lines, one line each. Never replace them with a paragraph.
    Backend tests: pytest <files or suites> against PostgreSQL 16: <N> passed.
                   or: Not applicable — <reason of 3+ words, e.g. the diff
                   changes only frontend files>.
    Frontend checks: npm test <N> passed; tsc --noEmit no errors; eslint
                   0 errors; next build succeeded.
    Migration test: <test name> passed (downgrade, upgrade, alembic check,
                   data preserved). or: Not applicable — no migration.
    Manual validation: what you did in the browser, at which widths, and what
                   you saw, acceptance test by acceptance test.
    Screenshots: what you captured (synthetic data), or why not.
  If a check could not run, write "Not run — because <reason>". The word
  "pending" is accepted only in a Draft PR.
- Title: specific and imperative. Not "Fix", "Update" or "Changes".
- Before opening the PR, run and pass:
    python scripts/validate_pr_description.py --body-file <body.md> \
      --title "<title>" --base origin/main --head HEAD
- Open the PR Ready for review only when every check above passed. Otherwise
  open it as Draft and list what is missing. Never merge.

Report back (to GPT, in plain language)
- What changed, for the user. Each acceptance test with its result.
- Checks run with their numbers. Anything not done, visual debt, open
  questions, and any open PR that may conflict.

---------------------------------------------------------------------
```

---

## Part D — Reviewing and merging (for the person who merges)

Merge one pull request at a time, oldest first unless one depends on another.

**Before merging, all of these must be true on the PR's latest commit:**

| Check | Where to look | Good |
| --- | --- | --- |
| PR Quality | Checks tab | ✅ green |
| Backend | Checks tab (required aggregate) | ✅ green — "skipped" groups are fine for frontend-only changes |
| Frontend | Checks tab | ✅ green |
| Conflicts | Bottom of the PR | "No conflicts with base branch" |
| Behaviour | PR text → Validation results → Manual validation | Every DONE WHEN check reported as passed |
| Safety | PR text | Synthetic data only; MUST NOT CHANGE respected |

**After each merge:** any other open PR that adds a database migration must be
brought up to date with main before it can merge; the agent renumbers it.

**When a PR fails:** ask the agent to fix it on the same branch. Never merge red.

---

## Example: a filled request (illustrative)

```text
REQUEST TYPE: Add
ONE OUTCOME: Company records show who may sign for the company and whose ID expires.

1. WHERE
   Module / screen:   Development > Company
   Record or section: a new "Authorised signatories" section under the company

2. WHAT I WANT
   Record each company's authorised signatories and the expiry of their ID.
   Why: banks and notaries refuse documents signed on an expired ID.

3. THE QUESTION THIS SCREEN SHOULD ANSWER
   Who can sign for this company today, and whose ID expires soon?
   Lead: the list of current signatories with an "ID expired" / "Expiring" pill.
   Behind a click: ID numbers and the scanned ID.

4. DATA
   Name (required, text); role (optional, text); ID number (optional, text);
   ID expiry (optional, date); scanned ID (optional, PDF up to 10 MB or Drive link).
   "Expiring" means within 60 days; the server decides.

5. NAMES AND WORDING
   New section title: "Authorised signatories". Pills: "ID expired", "Expiring".

6. WHO
   See: anyone who can see Company. Add/edit/delete: admins, project managers, finance.

7. DELETE / REMOVE BEHAVIOUR
   Delete with a reason; keep the record and its PDF in history.

8. MUST NOT CHANGE
   Bank accounts and company documents stay as they are.

9. DONE WHEN
   1. I add two made-up signatories; one with an ID that expired last month
      shows the red "ID expired" pill.
   2. One expiring in 30 days shows "Expiring".
   3. I delete the other with a reason and it disappears from the list but
      shows in history.

10. REFERENCE
   Look like the Registration documents rows on the same page.
```

## Example: a rename (illustrative)

```text
REQUEST TYPE: Change
ONE OUTCOME: The Authorities section is called NOS everywhere.

1. WHERE
   Module / screen: Development > Authorities

2. WHAT I WANT
   Rename the section to NOS. Why: that is what the team calls these permits.

5. NAMES AND WORDING
   Authorities → NOS
   Where: everywhere (menu, breadcrumb, page title, buttons such as
   "Add NOS expense", empty and error messages).

8. MUST NOT CHANGE
   Expense amounts, statuses and categories.

9. DONE WHEN
   1. The menu, breadcrumb and page title all read NOS.
   2. No visible text on that section still says Authorities.
```

## Example: a removal (illustrative)

```text
REQUEST TYPE: Remove
ONE OUTCOME: The unused Internal reference field disappears from Agreements.

1. WHERE
   Module / screen: Commercial > Agreements
   Record or section: the "Internal reference" field

2. WHAT I WANT
   Nobody uses it; take it off the form and the register.

4. DATA
   Existing values must be kept in the database and visible in the record's history.

7. DELETE / REMOVE BEHAVIOUR
   Retire the field: hide it from entry and display, keep stored values, no data deletion.

8. MUST NOT CHANGE
   Agreement status and dates.

9. DONE WHEN
   1. The field no longer appears on the form, register or record page.
   2. An old agreement with a value in that field still opens without errors.
```
