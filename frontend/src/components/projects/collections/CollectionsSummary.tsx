"use client";

import { Stat, StatRow, TableScroll } from "@/components/ui";
import type { CollectionProjectSummary } from "@/lib/api";
import { businessDate, money } from "@/lib/format";

import { AGING_BUCKETS, bucketLabel } from "./labels";

/**
 * The project's collections position, as at a stated date.
 *
 * Every figure here came back from the API on this request. Nothing is
 * totalled, netted or projected in the browser.
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
  currencyCode,
}: {
  summary: CollectionProjectSummary;
  currencyCode: string | null;
}) {
  return (
    <div className="stack">
      <StatRow>
        <Stat
          label="Outstanding"
          value={money(summary.outstanding_total, currencyCode)}
          note={`${summary.accounts} account${summary.accounts === 1 ? "" : "s"}`}
        />
        <Stat
          label="Due now"
          value={money(summary.due_total, currencyCode)}
          note="Reached its date, still owed"
        />
        <Stat
          label="Overdue"
          value={money(summary.overdue_total, currencyCode)}
          note={`${summary.accounts_overdue} account${
            summary.accounts_overdue === 1 ? "" : "s"
          } past grace`}
        />
        <Stat
          label="Unapplied cash"
          value={money(summary.unapplied_cash, currencyCode)}
          note="Confirmed, not yet applied"
        />
      </StatRow>
      <StatRow>
        <Stat
          label="Confirmed receipts (lifetime)"
          value={money(summary.confirmed_receipts_total, currencyCode)}
          note={`All cash confirmed to ${businessDate(summary.as_of)}`}
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

      <TableScroll label="Outstanding by age">
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
                {money(summary.buckets[bucket] ?? "0.00", currencyCode)}
              </td>
            ))}
          </tr>
        </tbody>
      </TableScroll>
    </div>
  );
}
