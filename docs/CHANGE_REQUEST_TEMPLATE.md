# Asking for a change

Anyone can ask Codex, Claude or another agent to add, change, remove or fix
something in Reach. Write what you want in plain words and start with one line:

```text
Read AGENTS.md first and follow it. Then: <what you want, in plain words>.
```

That is enough. `AGENTS.md` tells the agent how to understand the request, ask
about anything unclear, build it to Reach's design and engineering rules, test
it with made-up data and open a pull request that passes the checks. If you
pass the request through GPT, ask GPT to forward it in your own words and add
nothing you did not say.

## Make it land first time (optional)

Each of these the agent would otherwise have to ask about or assume:

- **Where** — the module and section, e.g. "Development > Land, the Site & utilities tab".
- **Why** — the business reason, one line.
- **Fields** — for each: required or optional, and text / date / money (which
  currency) / percentage / file / Drive link / choice (list the choices).
- **Wording** — exact labels; for a rename, "everywhere" or the places to change.
- **Who** — who can see it, edit it and delete it.
- **Done when** — two or three checks you will do yourself.
- **Must not change** — anything that has to stay exactly as it is.

Never paste real customer, buyer or company data. Describe it, or make up an example.

### Examples

```text
Read AGENTS.md first and follow it. Then: rename the Authorities section to NOS
everywhere — menu, page title, buttons and messages. Amounts and statuses must
not change.
```

```text
Read AGENTS.md first and follow it. Then: in Development > Company, record each
company's authorised signatories: name (required), role, ID number, ID expiry
date and a scanned ID (PDF or Drive link). Show an "ID expired" pill when the
date has passed. Admins, project managers and finance can add, edit and delete
with a reason. Done when I can add two, one shows "ID expired", and I can
delete the other.
```

```text
Read AGENTS.md first and follow it. Then: on a land parcel, the "Available
subject to conditions" option spills out of its box on desktop. Fix it.
```

## Before you merge

Merge one pull request at a time. On the pull request's latest commit:

| Check | Good |
| --- | --- |
| PR Quality, Backend, Frontend (Checks tab) | All green. Skipped backend groups are fine for screen-only changes. |
| Bottom of the pull request | No conflicts and not out of date with main. |
| Validation results, in the description | Your "done when" checks are reported as passed. |
| Review focus, in the description | You agree with any assumptions the agent listed. |

After each merge, other open pull requests fall behind main and need updating
before they can merge. Never merge a red pull request; ask the agent to fix it on
the same branch.
