"use client";

import {
  Distribution,
  DistributionBand,
  Metric,
  MetricGroup,
  Position,
  PositionFigure,
  PositionSupport,
  PositionSupportItem,
  SectionHeader,
} from "@/components/ui";
import type { CollectionCurrencyTotals, CollectionProjectSummary } from "@/lib/api";
import { businessDate, isPositive, money } from "@/lib/format";

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
 * balance invites exactly the wrong subtraction. And **Unapplied cash** is on
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
  return (
    <div className="stack stack-tight">
      {summary.currencies.length === 0 ? (
        <p className="footnote">No accounts have a governing schedule yet.</p>
      ) : null}

      {summary.currencies.map((totals) => (
        <CurrencyBlock
          key={totals.currency_id}
          totals={totals}
          asOf={summary.as_of}
          code={currencyCodeOf(totals.currency_id)}
          showHeading={summary.currencies.length > 1}
        />
      ))}

      <MetricGroup compact>
        <Metric label="Accounts" value={summary.accounts} size="sm" note={`As at ${businessDate(summary.as_of)}`} />
        <Metric
          label="Overdue"
          value={summary.accounts_overdue}
          size="sm"
          note="Past grace"
          tone={summary.accounts_overdue > 0 ? "danger" : "neutral"}
        />
        <Metric
          label="Disputed"
          value={summary.accounts_disputed}
          size="sm"
          note="Contested, still counted"
          tone={summary.accounts_disputed > 0 ? "danger" : "neutral"}
        />
        <Metric label="Cleared" value={summary.accounts_cleared} size="sm" note="Nothing owed, nothing unapplied" />
      </MetricGroup>
    </div>
  );
}

/**
 * How old a band's money is, in the order the server ages it.
 *
 * A band marker, not a measurement: the rule above each band warms as the
 * money gets older, and no width anywhere encodes an amount.
 */
const BUCKET_HEAT: Record<string, "cool" | "warm" | "hot" | "late"> = {
  awaiting_trigger: "cool",
  current: "cool",
  "1_30": "warm",
  "31_60": "warm",
  "61_90": "hot",
  "91_plus": "late",
};

function CurrencyBlock({
  totals,
  asOf,
  code,
  showHeading,
}: {
  totals: CollectionCurrencyTotals;
  asOf: string;
  code: string | null;
  showHeading: boolean;
}) {
  return (
    <div className="currency-block">
      {showHeading ? (
        <p className="currency-block-title">
          {code ?? "Unknown currency"}
          <span className="muted">
            · {totals.accounts} account{totals.accounts === 1 ? "" : "s"}
          </span>
        </p>
      ) : null}

      <Position compact>
        <PositionFigure lead label="Outstanding" value={money(totals.outstanding_total, code)} />
        <PositionFigure
          label="Due now"
          value={money(totals.due_total, code)}
          note="Reached its date, still owed"
        />
        <PositionFigure
          label="Overdue"
          value={money(totals.overdue_total, code)}
          note="Past grace"
          tone={isPositive(totals.overdue_total) ? "danger" : "neutral"}
        />
        <PositionFigure
          label="Unapplied cash"
          value={money(totals.unapplied_cash, code)}
          note="Confirmed, not yet applied"
          tone={isPositive(totals.unapplied_cash) ? "warning" : "neutral"}
        />
      </Position>
      <PositionSupport>
        <PositionSupportItem
          label="Confirmed receipts, lifetime"
          value={money(totals.confirmed_receipts_total, code)}
        />
        <PositionSupportItem label="All cash confirmed to" value={businessDate(asOf)} />
      </PositionSupport>

      <SectionHeader title="Outstanding by age" />
      <Distribution>
        {AGING_BUCKETS.map((bucket) => (
          <DistributionBand
            key={bucket}
            label={bucketLabel(bucket)}
            value={money(totals.buckets[bucket] ?? "0.00", code)}
            heat={BUCKET_HEAT[bucket] ?? "cool"}
          />
        ))}
      </Distribution>
    </div>
  );
}
