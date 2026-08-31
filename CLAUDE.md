# Working in this repository

Conventions a coding agent needs before touching anything here. The reasoning
lives in `docs/ENGINEERING_RULES.md`; this file is the short form.

## Continuous integration runs at two speeds

GitHub's draft state is the switch, and nothing else selects it.

```text
Draft               Backend Fast   structural checks + the tests this change
                                   can plausibly break        (minutes)
Ready for review    Backend        structural checks + every test    (~45 min)
```

Fast CI is not weaker CI. It answers *did I break the area this change can
reasonably affect?*; the full suite still answers *is this exact commit safe
for the whole application?* before anything merges.

## How to run a piece of work

1. Branch from current `main` — `mvp/pr-NN-slug` for roadmap work,
   `eng/pr-NN-slug` for engineering work that adds no functional scope.
2. Implement.
3. Run the affected domain's tests locally, plus `ruff check .` and
   `ruff format --check .`. You do **not** need `pytest -q` after every edit.
   To see what CI would pick:
   `python scripts/ci_backend_tests.py --changed <paths>`
4. **Open the pull request as a draft.**
5. Wait for `Backend Fast` and `Frontend`. Stop for independent review.
6. Fix review findings while still a draft — each round costs a fast run, not a
   full one.
7. When review says the code is a final candidate, run the full suite locally
   once if practical, then mark the pull request **ready for review**.
8. Wait for `Backend` (full) and `Frontend` on the exact head.
9. Stop. **Never merge.** A human merges.

Any commit pushed after the pull request is ready re-runs the full suite, so
never recommend merging on a green run whose head SHA is not the current one.

## Adding a domain to the fast selector

When a new module lands, `scripts/ci_backend_tests.py` needs two lines — an
entry in `DOMAIN_TEST_PREFIXES` and, if anything consumes it, **one** edge in
`DOWNSTREAM`. Only one: the closure is transitive, so adding
`payment_plans -> collections` is enough for a pricing change to reach
collections. Until a module is mapped it falls back to the full suite, which is
the intended behaviour, not a bug. Guard tests fail if any test file belongs to
no domain, or if the dependency graph gains a cycle.

## Things that are never acceptable

- Skipping, disabling, quarantining or deleting a test to get a build green.
- Substituting SQLite for PostgreSQL in any test. Row locks, partial unique
  indexes and `NUMERIC` are the behaviour under test.
- Adding a dependency without justifying why the standard library and the
  existing framework will not do.
- Merging, or recommending a merge, from a draft pull request.
