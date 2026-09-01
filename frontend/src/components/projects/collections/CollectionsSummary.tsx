"use client";

import { Stat, StatRow, TableScroll } from "@/components/ui";
import type { CollectionCurrencyTotals, CollectionProjectSummary } from "@/lib/api";
import { businessDate, money } from "@/lib/format";

import { AGING_BUCKETS, bucketLabel } from "./labels";

/**
 * The project's collections position, as at a stated date.
 *
 * Every figure here came back from the API on this request. Nothing is
 * totalled, netted or projected in the browser.
 *
 * **Money is shown one denomination at a time, and never added across them.**
 * A project can sell in more than one currency, and a single "outstanding"
 * figure for such a project could only be produced by adding unlike numbers and
 * then labelling the sum with whichever currency happened to come first. The
 * API refuses to produce that number, and this screen refuses to assemble one:
 * each denomination gets its own block, with its own code beside every figure.
 *
 * Two labels are doing real work. **Confirmed receipts** says *lifetime*,
 * because an unqualified "Collected" sitting beside a current outstanding
 * balance invites exactly the wrong subtraction — a reader would take one from
 * the other and get a number that means nothing. And **Unapplied cash** is on
 * the strip at all because money that has arrived and not been assigned to an
 * instalment is a live operational problem: it is the buyer's money, it is in
 * the company's account, and nobody has decided what it settles.
 */
export function CollectionsSummary({
  summary,
  currencyCodeOf,
}: {
  summary: CollectionProjectSummary;
  currencyCodeOf: (id: string | null | undefined) => string | null;
}) {
  const plural = (count: number, word: string) =>
    `${count} ${word}${count === 1 ? "" : "s"}`;

  return (
    <div className="stack">
      <StatRow>
        <Stat
          label="Accounts"
          value={summary.accounts}
          note={
            summary.currencies.length > 1
              ? `${summary.currencies.length} currencies, reported separately`
              : `As at ${businessDate(summary.as_of)}`
          }
          small
        />
        <Stat
          label="Accounts overdue"
          value={summary.accounts_overdue}
          note="Past grace"
          small
        />
        <Stat
          label="Accounts disputed"
          value={summary.accounts_disputed}
          note="Contested, and still counted"
          small
        />
        <Stat
          label="Accounts cleared"
          value={summary.accounts_cleared}
          note="Nothing owed, nothing unapplied"
          small
        />
      </StatRow>

      {summary.currencies.length === 0 ? (
        <p className="muted">No accounts have a governing schedule yet.</p>
      ) : null}

      {summary.currencies.map((totals) => (
        <CurrencyBlock
          key={totals.currency_id}
          totals={totals}
          asOf={summary.as_of}
          code={currencyCodeOf(totals.currency_id)}
          showHeading={summary.currencies.length > 1}
          plural={plural}
        />
      ))}
    </div>
  );
}

function CurrencyBlock({
  totals,
  asOf,
  code,
  showHeading,
  plural,
}: {
  totals: CollectionCurrencyTotals;
  asOf: string;
  code: string | null;
  showHeading: boolean;
  plural: (count: number, word: string) => string;
}) {
  return (
    <div className="stack">
      {showHeading ? (
        <h3 className="section-heading">
          {code ?? "Unknown currency"}
          <span className="muted"> · {plural(totals.accounts, "account")}</span>
        </h3>
      ) : null}

      <StatRow>
        <Stat
          label="Outstanding"
          value={money(totals.outstanding_total, code)}
          note={plural(totals.accounts, "account")}
        />
        <Stat
          label="Due now"
          value={money(totals.due_total, code)}
          note="Reached its date, still owed"
        />
        <Stat
          label="Overdue"
          value={money(totals.overdue_total, code)}
          note="Past grace"
        />
        <Stat
          label="Unapplied cash"
          value={money(totals.unapplied_cash, code)}
          note="Confirmed, not yet applied"
        />
      </StatRow>
      <StatRow>
        <Stat
          label="Confirmed receipts (lifetime)"
          value={money(totals.confirmed_receipts_total, code)}
          note={`All cash confirmed to ${businessDate(asOf)}`}
          small
        />
      </StatRow>

      <TableScroll label={code ? `Outstanding by age (${code})` : "Outstanding by age"}>
        <thead>
          <tr>
            {AGING_BUCKETS.map((bucket) => (
              <th key={bucket} scope="col" className="num">
                {bucketLabel(bucket)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          <tr>
            {AGING_BUCKETS.map((bucket) => (
              <td key={bucket} className="num mono">
                {money(totals.buckets[bucket] ?? "0.00", code)}
              </td>
            ))}
          </tr>
        </tbody>
      </TableScroll>
    </div>
  );
}
