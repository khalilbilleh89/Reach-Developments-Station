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

The user's explicit instructions take precedence over repository guidance.
