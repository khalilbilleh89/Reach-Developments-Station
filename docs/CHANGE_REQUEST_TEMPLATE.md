# Change request template (for Claude, Codex or any agent)

Copy the block below into a new conversation or task whenever you want a pull
request that **adds**, **changes** or **removes** something in Reach. Fill in the
owner part in plain business language; leave the standing instructions as they
are. They are the same on every device, so work submitted from a phone, a laptop
or another agent lands on the same design system.

The standing instructions only *point* at the rules. The rules themselves live
in [UX_SYSTEM.md](UX_SYSTEM.md), the
[Experience 6 catalogue](design-system/README.md), [AGENTS.md](../AGENTS.md),
[ENGINEERING_RULES.md](ENGINEERING_RULES.md) and
[DELETION_POLICY.md](DELETION_POLICY.md). If one of those changes, this template
does not need to.

---

```text
REQUEST TYPE: Add | Change | Remove            (pick one)

1. WHERE
   Module / screen: (e.g. Development > Company, Delivery > Reports, Sales > Buyers)
   Record or section: (e.g. the bank account block, the report register)

2. WHAT I WANT
   In one or two sentences, in business words:
   (e.g. "Record each company's authorised signatories with their ID expiry date.")

3. THE QUESTION THIS SCREEN SHOULD ANSWER
   What do I need to know at a glance when I open it?
   (e.g. "Who can sign for this company, and is anyone's ID about to expire?")
   What should lead / be most visible:
   What can sit behind a click (secondary detail):

4. DATA
   Fields to add / change / remove, and for each: required or optional,
   text / date / money (which currency) / percentage / file / Drive link / choice
   (list the choices):
   Existing data that must be preserved or migrated:

5. WHO
   Who can see it:            (e.g. finance and admins only)
   Who can add / edit:
   Who can delete:

6. DELETE / REMOVE BEHAVIOUR
   For Add: how should Delete work? What blocks it (linked records)?
   For Remove: remove the feature, hide it, or retire it but keep history?
   What history or evidence must be kept:

7. MUST NOT CHANGE
   (e.g. "Do not change how collections are calculated.")

8. DONE WHEN
   How I will check it works:
   (e.g. "I can add two signatories, see the expiring one flagged, and delete one.")

9. REFERENCE (optional)
   Screenshots, a similar screen in Reach to copy, or an example document:

---------------------------------------------------------------------------
STANDING INSTRUCTIONS FOR THE AGENT (do not edit)

Before writing code:
- Follow CLAUDE.md and AGENTS.md. Read docs/ENGINEERING_RULES.md and
  docs/DELETION_POLICY.md.
- For any screen work, load the .claude/skills listed in AGENTS.md:
  frontend-product-design, frontend-implementation, frontend-review, and
  financial-ui-integrity for amounts, rates, percentages or dates. Read the
  matching section of docs/UX_SYSTEM.md (§8 for workspaces) and the component
  entry in docs/design-system/README.md.
- Find the nearest existing Reach screen that does the same job and match it.
  If the request conflicts with a rule, or changes which figure a page leads
  with, ask me before building.

While building:
- Compose only from @/components/ui primitives and the approved catalogue
  entries. No new colours, no screen-local component copies, no side drawers.
- Lead with the answer to question 3. Show entered values at full weight; say
  what is missing once, in muted text, not as a column of "Not entered".
- Sentence-case headings and labels. One primary (gold) action per view.
  Secondary row actions go in the row menu (⋯); a lone action stays visible.
- Short fixed choices are segmented controls or choice cards; lists that grow
  with data stay dropdowns. Long forms (3+ sections) get section links and the
  sticky save bar.
- Show loading, empty, denied and failed as different states. The browser never
  calculates money.
- Every Add ships with a working, reasoned, audited Delete (AGENTS.md).

Before opening the PR:
- Run the checks in CLAUDE.md (frontend lint, tsc, tests, build; Product
  Experience guards; Ruff and PostgreSQL tests when Python changes).
- Render the changed screens with realistic synthetic data at 1440px and 390px
  and compare before/after. Name any visual debt left.
- Fill every section of .github/pull_request_template.md. Open it ready for
  review once checks pass. Never merge.
---------------------------------------------------------------------------
```

---

## Example: a filled request (illustrative)

```text
REQUEST TYPE: Add

1. WHERE
   Module / screen: Development > Company
   Record or section: a new "Authorised signatories" section under the company

2. WHAT I WANT
   Record each company's authorised signatories and the expiry of their ID.

3. THE QUESTION THIS SCREEN SHOULD ANSWER
   Who can sign for this company today, and whose ID expires soon?
   Lead: the list of current signatories with an "ID expired" / "Expiring" pill.
   Behind a click: ID numbers and the scanned ID.

4. DATA
   Name (required, text); role (optional, text); ID number (optional, text);
   ID expiry (optional, date); scanned ID (optional, PDF up to 10 MB or Drive link).

5. WHO
   See: anyone who can see Company. Add/edit/delete: admins, project managers, finance.

6. DELETE / REMOVE BEHAVIOUR
   Delete with a reason; keep the record and its PDF in history.

7. MUST NOT CHANGE
   Bank accounts and company documents stay as they are.

8. DONE WHEN
   I add two signatories, one with an expired ID shows the red pill, and I can
   delete the other.

9. REFERENCE
   Look like the Registration documents rows on the same page.

(standing instructions block unchanged)
```

## Example: a removal (illustrative)

```text
REQUEST TYPE: Remove

1. WHERE
   Module / screen: Commercial > Agreements
   Record or section: the "Internal reference" field

2. WHAT I WANT
   Nobody uses it; take it off the form and the register.

3. THE QUESTION THIS SCREEN SHOULD ANSWER
   Unchanged.

4. DATA
   Existing values must be kept in the database and visible in the record's history.

5. WHO
   Unchanged.

6. DELETE / REMOVE BEHAVIOUR
   Retire the field: hide it from entry and display, keep stored values, no data deletion.

7. MUST NOT CHANGE
   Agreement status and dates.

8. DONE WHEN
   The field no longer appears on the form, register or record page, and old
   agreements still open without errors.

(standing instructions block unchanged)
```
