# Required development behavior

Read `docs/ENGINEERING_RULES.md` and `docs/DELETION_POLICY.md` before changing this repository.

## Every created record needs deletion

The owner requires a visible **Delete** action for every user-created record, including
configuration choices and child rows. Treat deletion as part of the feature, not a follow-up.
Do not deliver Add/Edit without completing the matching deletion flow.

- Implement the button, confirmation, API client, server authorization, project/phase
  isolation, dependency handling, audit event, and register refresh together.
- Draft and unused records must have a working removal path. Never use an always-failing
  endpoint or a cosmetic button to satisfy this requirement.
- Preserve posted financial, legal, approval, and audit evidence. Explain blocked states
  and provide the appropriate cancellation, reversal, retirement, or retained removal
  workflow. Do not silently cascade into linked business records.
- Test success, denied roles, wrong scope, linked records, repeated requests, and audit
  retention. Check the actual UI location, not just the presence of an API.
- Update `docs/deletion_contracts.json` and the deletion section of the PR template.
  Existing audited gaps do not authorize new gaps. Do not claim system-wide completion
  while the audit still records missing implementations.
- Apply this checklist on every future feature, even when the user does not repeat it.

## Full pages, never side drawers

Use a full page for record creation, editing, detail, inspection and drilldowns.
Side drawers, slide-overs and narrow side inspectors are prohibited at every viewport.
Use `RecordPage` for state-owned flows in the shared shell, or an existing routed page.
Keep Back navigation, register state, unsaved-change protection and deletion controls.
Small centered confirmations, reason prompts and short forms are allowed.
Mobile navigation must also use a full-width page. See `docs/UX_PAGE_AUDIT.md`.

## Task-specific skills

`.claude/skills/` holds task-specific expertise that does not belong in these permanent
rules. Each skill is one `SKILL.md` with a `description` saying when it applies. Before
starting a task, read the description of each skill below and open the matching
`.claude/skills/<skill>/SKILL.md` in full when the current task matches it. Skills point
to the canonical sources; they do not replace them.

| Skill | Read it when |
| --- | --- |
| `frontend-product-design` | Designing or redesigning a page, workspace, card, register, record header or analysis section |
| `frontend-implementation` | Writing TypeScript or CSS under `frontend/`, or before pushing a frontend diff |
| `frontend-review` | Reviewing a frontend change, your own or someone else's, or when a UI guard fails |
| `financial-ui-integrity` | Touching an amount, currency, total, ratio, progress bar, chart, business date, or the states around them |
| `real-estate-product-workflow` | Changing what a record means — inventory, pricing, sales, payment plans, collections, commissions, construction, cashflow or management actions |

One skill is the single source of truth for its subject. Do not copy skill content into
this file or into `CLAUDE.md`.

## Owner requests

Requests usually arrive as a few plain sentences ("add X to Y", "rename A to B",
"Z is broken"), not a filled template. Turn them into a correct change yourself:

1. **Understand before building.** Restate the request as one outcome. Find the
   module and the nearest existing Reach screen that does the same job. If a detail
   that changes what you build is missing — the fields and their types, who can see,
   edit or delete, how deletion behaves, what "done" means — ask. If you cannot ask,
   choose the smallest assumption consistent with the rules above and list every
   assumption under the PR's Review focus.
2. **One request, one branch, one PR.** Branch from the latest `origin/main`. Split a
   request with independent outcomes. Check open PRs for the same files or another
   new migration and name any overlap under Review focus.
3. **Build with the skills above** and the design system. Use the requester's words
   for labels. A rename changes every user-visible place: menu, breadcrumb, page
   title, buttons, empty and error messages, exports and tests.
4. **Synthetic data only** in code, tests, fixtures, screenshots and PR text. Never
   name, open or test against production records.
5. **Migrations.** Fetch `origin/main` first; number = current Alembic head + 1 and
   `down_revision` = that head. In the same PR set `HEAD_REVISION` in
   `tests/test_migrations.py`, add the revision to `scripts/ci_backend_tests.py` and
   `scripts/ci_backend_smoke.py`, and add a test that downgrades to its own parent,
   upgrades to head, runs `alembic check` and proves existing data survived. Never
   hard-code a later revision in a test. A downgrade restores the old shape or refuses
   while new data exists; it never silently drops data.
6. **Verify.** Run the checks in `CLAUDE.md` for what changed, never skipping or
   weakening a test. Render each changed screen with synthetic data at 1440px and
   390px and walk through what the requester will check.
7. **Report back** in plain language: what changed, how to check it, assumptions,
   anything not done and any visual debt.

`docs/CHANGE_REQUEST_TEMPLATE.md` lists the details a requester can add up front;
a request without it follows the same steps.

## Agent automation

CI scope is determined by code risk, not pull-request size or Draft/Ready state.
Product changes run their domain, direct consumers and the invariant pack;
foundational system changes may require complete regression. Never add `ci:full`
"just to be safe": explain the system-wide or hidden-integration blast radius
that makes the optional Full Backend Shadow useful. See `docs/CI_STRATEGY.md`.

Reusable safety and preflight checks live under `scripts/`, not inside any one agent's
configuration. Before declaring implementation work complete, run:

```
python scripts/agent_preflight.py
```

It checks only what changed — formatting, lint, JSON that no longer parses, conflict
markers, tracked secret files — and reports what it could not run rather than passing
silently. CI remains the authority on correctness. See `docs/AGENT_AUTOMATION.md`.

Do not reimplement these checks in agent-specific instructions.

## Pull requests are engineering deliverables

Every PR must use `.github/pull_request_template.md` and satisfy PR Quality.
Before opening or updating a PR:

- inspect repository reality; explain root cause, scope and non-goals;
- declare contract, migration, financial, security and deletion impact;
- report only validation that actually ran; state unavailable/pending evidence explicitly;
- explain why broad changes belong together, or split them;
- keep the PR Draft until its implementation and description are reviewable.

PR Quality reads the description mechanically. Answer in the template's shape:

- **CI phase:** tick exactly one box, matching the PR's real state.
- **Contract Impact / Migration Impact:** each line is exactly `Yes` or `No`,
  optionally followed on the same line by ` — reason`. Put explanations *above* the
  fenced block; text below it is read as part of the last answer.
- **Validation results:** keep the five labelled lines, one line each, never a
  paragraph. Name the command and the count, e.g.
  `Backend tests: pytest tests/modules/test_parcels.py against PostgreSQL 16: 48 passed.`
  `Frontend checks: npm test 338 passed; tsc --noEmit no errors; eslint 0 errors; next build succeeded.`
  Use `Not applicable — <reason>` or `Not run — because <reason>`; "pending" is
  valid only in a Draft.
- Run `python scripts/validate_pr_description.py --body-file <body.md> --title
  "<title>" --base origin/main --head HEAD` and open Ready only after it passes and
  the checks ran. Never merge.

A generated commit summary is not a PR description. Do not replace the template
with a short AI-generated summary. This applies to every agent, human and device.

The user's explicit instructions take precedence over repository guidance.
