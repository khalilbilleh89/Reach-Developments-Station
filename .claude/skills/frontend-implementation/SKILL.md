---
name: frontend-implementation
description: Build or change Reach frontend code — components, tabs, registers, record pages, forms, dialogs and the stylesheet. Use when writing TypeScript or CSS under frontend/, adding a screen or field, wiring an API call, or before pushing any frontend diff.
---

# Building a screen in Reach

The frontend is a **Next.js static export served by FastAPI from
`frontend/out`**. There is no component library, no icon package, no CSS-in-JS,
no chart package, no state-management library and no web font request. That is
a deliberate standing constraint, not an omission waiting to be fixed.

## Read before you write

| Source | What it owns |
| --- | --- |
| `docs/ENGINEERING_RULES.md` §5 | Frontend clean-code rules — the frontend renders backend truth, API access centralises under `frontend/src/lib/api/`, `any` needs written justification, one responsibility per component, no global state library |
| `docs/ENGINEERING_RULES.md` §2 | Dependency policy. Adding a package is a declared decision, not a convenience |
| `docs/UX_SYSTEM.md` §5, §7, "Form safety and request outcomes" | The primitive table, record/form rules, `DraftBoundary`, `requestFormLeave`, reason-dialog behaviour |
| `frontend/src/components/ui/index.ts` | Every primitive that exists, with the doc comment explaining why there are no aliases |
| `frontend/src/lib/answer.ts` | `useAnswer` and the five answers a request can give |
| `frontend/src/lib/roles.ts` | The role sets mirroring `permissions.py`; affordances, never security |
| `frontend/src/lib/format.ts`, `frontend/src/lib/currency.tsx` | `money()`, business dates, currency-id resolution |
| `AGENTS.md`, `docs/DELETION_POLICY.md` | Every created record needs a working Delete |

## Rules with teeth

These are enforced by `tests/test_product_experience.py`, which fails the build.
Know them before the guard tells you.

- **One primitive system.** Import from `@/components/ui`. No second name for an
  existing component, no `CardV4`, no screen-local reimplementation. `Panel`,
  `Stat`, `StatRow` and `FilterBar` are retired and stay retired.
- **One stylesheet layer.** All literal colours live in the single top-level
  `:root` block in `frontend/src/app/globals.css`. A component scope may alias
  those tokens; it may not introduce a hex value or an override theme.
- **Every tab strip is the same strip.** `Tabs` has no `variant` prop and no
  templated class name. One appearance, one keyboard contract.
- **The browser does no financial arithmetic.** See the
  `financial-ui-integrity` skill. This is the guard that catches the most.
- **Only entitled readers ask.** Gate the request on the reader's roles before
  fetching (`useAnswer(enabled, …)`), so figures a role may not read never reach
  the browser. The server checks again regardless; hiding a rendered field is
  not enforcement.
- **Full pages, never drawers.** `RecordPage` for state-owned record flows, or a
  routed page. Small centred confirmations, reason prompts and short forms stay
  dialogs. This holds at every viewport, mobile navigation included.
- **Delete ships with Add.** A creation flow without a discoverable, working,
  server-authorised removal path is incomplete. `docs/deletion_contracts.json`
  and the PR template both record it.

## Method

1. **Find the screen that already does this.** `frontend/src/components/projects/`
   and `frontend/src/components/dashboard/` hold real examples of registers,
   record pages, tabs, forms and dialogs. Match the closest one rather than
   inventing a shape.
2. **Add the API call under `frontend/src/lib/api/`,** typed, next to its
   siblings. Components never call `fetch`. Do not duplicate a domain type that
   `frontend/src/lib/api/types.ts` already declares.
3. **Wrap the read in `useAnswer`** with the role gate, and render all five
   answers. `off`, `loading`, `ready`, `denied` and `failed` are different
   screens. A failure is said in words; it is never a row of zeros.
4. **Compose from the primitives.** If a primitive needs a new capability,
   extend it there — one change, every screen.
5. **Protect the draft.** State-owned inline editors use `DraftBoundary`
   compared against the saved record; inline close/version controls carry
   `data-leaves-editor`; non-link project selection that replaces an editor uses
   `requestFormLeave`. Never persist a customer or transaction draft in storage.
6. **Give the deletion path the same attention as the creation path.**

## Anti-patterns this repository has actually shipped

- **A fixture shaped like the answer.** A test supplied `currency_id: "EUR"` —
  a code where production sends a UUID — so the test passed while the live page
  printed a raw UUID to the owner. Fixtures must have the *shape production
  sends*, not the shape that makes the assertion pass.
- **A guard that matched its own explanation.** An assertion scanning for the
  word `variant` matched the comment saying the variant was removed. When a
  guard is wrong, make it *more precise*, never looser.
- **A new test file nobody claimed.** `tests/` files must be registered in
  `scripts/ci_backend_tests.py`; an unregistered one fails
  `test_every_test_file_in_the_repository_is_claimed_by_something`.
- **Running only the checks that match the diff's file extension.** A frontend
  change that edits one Python guard still has to pass Ruff.

## Validation before you push

Run from the repository root unless noted. `docs/ENGINEERING_RULES.md` §12 is
the full definition of done; this is the frontend subset.

```bash
cd frontend && npm run lint          # ESLint
cd frontend && npx tsc --noEmit      # TypeScript
cd frontend && npm test              # node --test tests/*.test.mjs
cd frontend && npm run build         # production static export (runs npm test first)
python -m pytest tests/test_product_experience.py -q
```

If the diff touches **any** `.py` file — including a guard you extended —
also run:

```bash
ruff check .
ruff format --check .
```

Add a frontend test in `frontend/tests/` for behaviour the guards cannot see.
The harness transpiles the component and walks the rendered tree; look at
`frontend/tests/overviewPosition.test.mjs` or `salesWorkspace.test.mjs` for the
pattern. Never skip, delete or weaken a test to obtain a green run.

Open the pull request as **Draft**. A human merges; agents do not.
