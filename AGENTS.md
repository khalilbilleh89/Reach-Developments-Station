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

The user's explicit instructions take precedence over repository guidance.
