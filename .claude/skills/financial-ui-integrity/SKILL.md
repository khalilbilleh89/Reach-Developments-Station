---
name: financial-ui-integrity
description: Display money, rates, percentages, counts and business dates truthfully in the Reach interface. Use whenever a change touches an amount, a currency, a total, a ratio, a progress bar, a chart, a date, or the loading/denied/failed/empty states around any of them.
---

# Money on screen

Every figure on a Reach screen is a claim about a contract, a receipt or a
commitment. There is exactly one rule beneath all the others: **the browser
displays what the server computed, and nothing else.**

## Read before you touch a figure

| Source | What it owns |
| --- | --- |
| `docs/UX_SYSTEM.md` §9 | The financial and business boundary in full — what `money()`, `Meter`, `CountComposition`, `CountSeries` and `DistributionTrack` may and may not do |
| `docs/ENGINEERING_RULES.md` §6 | Money, rates, dates, derived values, status dimensions, financial and legal deletion |
| `frontend/src/lib/format.ts` | `money()`, business dates, rate formatting — and the doc comment saying why no JavaScript Number is ever constructed |
| `frontend/src/lib/currency.tsx` | `CurrencyProvider` and `useCurrencyCode()` |
| `frontend/src/lib/answer.ts` | The five answers a request can give |
| `tests/test_product_experience.py` | `TestTheBrowserDoesNoFinancialArithmetic`, `TestOnlyEntitledReadersAsk` |

## The boundary

**Money is a string, end to end.** It arrives as an exact decimal string and
stays one. `money()` groups the existing digits and attaches a resolved currency
code. No `Number()`, no `parseFloat`, no rounding, no scale change, no
conversion — a float is an approximation and nothing on a contract screen may be
approximate.

**No browser arithmetic.** No sums, ratios, margins, forecasts, economics,
derived progress or invented financial series. If the page needs a total, the
API returns the total. If it does not, the page does not show one.

**Never infer a financial total from visible rows.** Rows are a page of a
register; their sum is not the figure.

**`Meter` shows a percentage the server already reported.** Never compute a
completion percentage for visual effect. Numerator, denominator and availability
stay visible. Neutral styling does not imply a risk threshold.

**Counts are not money.** `CountComposition` and `CountSeries` render integer
counts the server returned; SVG arithmetic may position them, nothing may
normalise a decimal string. Keep negative observations, zeros, the exact printed
counts, the period labels and an accessible text equivalent. Legal, commercial,
collection and delivery are separate dimensions and never merge.

**Physical progress is not financial progress.** Do not combine them.

**A new financial plot needs an owning API's comparable source series** and safe
normalised geometry and basis before it may exist. The Collections ageing track
is that rule satisfied, not an exception to it.

## Currency

**A `currency_id` is a UUID. It is not a currency code.**

Records that carry money — price versions, reservations, contracts, tax lines,
benchmarks — name their denomination by `currency_id`. The code comes from
`useCurrencyCode()`, which reads the register `ProjectWorkspace` loaded and
seeded with the project's base and reporting pair:

```tsx
const codeOf = useCurrencyCode();
const amountCode = codeOf(record?.currency_id) ?? projectCurrencyCode;
```

An id the map cannot resolve yields `null`, and the figure is shown
**undenominated** rather than labelled with a guess.

**Resolve each record's own denomination.** Never assume the project's currency
for a row that carries its own. Never combine different currencies — a capital
band selects records by currency and metric code without summing across them.

### This has actually gone wrong here

A dashboard card passed `purse.currency_id` straight into `money()`. The live
page printed a raw UUID beside an amount, in front of the owner. The test suite
was green, because the fixture used `currency_id: "EUR"` — a fixture shaped like
the answer rather than like what production sends.

Two standing consequences:

1. Fixtures carry production's shape. Currency ids are UUIDs in every fixture.
2. Assert that no UUID appears anywhere in the rendered tree.

## Dates

A business date is a calendar fact with no time and no timezone. It never goes
through `new Date(...)` — a `Date` pins it to an instant and can render it as the
previous day elsewhere. Read the string as components and format the components.
System timestamps (`created_at` and friends) get the timestamp treatment, which
is a different thing. Business dates never undergo timezone conversion.

## The six states of a figure

`loading`, `absent`, `denied`, `failed`, `partial` and `zero` are six different
facts and must look different:

| State | What it means | How it is drawn |
| --- | --- | --- |
| `off` | The reader's role was never entitled, or there is nothing to ask | Not rendered at all |
| `loading` | The request is in flight | A loading shape, never stale figures |
| `denied` | The server refused this reader (403) | "Not available to your role", or nothing |
| `failed` | The request faulted | Said in words, with Retry |
| absent / partial | The server answered, coverage is incomplete | Coverage and sample size stated explicitly |
| zero | The server answered, and the figure is zero | The figure, labelled |

**Keep a failure visible. Never replace it with a comforting zero or a false
empty state.** A screen that turns an error into `0.00` is worse than a screen
that is blank, because someone will act on it.

**Never label amounts from a previous date or filter as current data.**
`useAnswer` pairs each result with its request identity for exactly this reason.

## Entitlement

Gate the request on the reader's role sets in `frontend/src/lib/roles.ts` before
fetching, so figures a role may not read never reach the browser. Those sets
mirror `permissions.py` frozensets; they are affordances, never security. The
server checks again on every call.

## Before you claim it is correct

```bash
python -m pytest tests/test_product_experience.py -q
cd frontend && npm test
```

Then look at the rendered screen with real loaded data and read every figure
against the API response that produced it. A green guard proves the shape; only
the response proves the number.
