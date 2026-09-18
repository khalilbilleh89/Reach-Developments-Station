"use client";

import type { CollectionCurrencyTotals, CollectionProjectSummary } from "@/lib/api";
import { businessDate, isPositive, money } from "@/lib/format";
import {
  Breakdown,
  BreakdownRow,
  Distribution,
  DistributionBand,
  DistributionTrack,
  PositionFigure,
  SectionHeader,
  StatStrip,
  StatStripItem,
  StatStripNote,
} from "@/components/ui";
import {
  AGING_BUCKETS,
  bucketHeatForAmount,
  bucketLabel,
} from "@/components/projects/collections/labels";

/**
 * The project's receivables: one figure, its ledger, and how old the money is.
 *
 * Outstanding is the figure a director opens the card for, so it stands alone
 * on the card's one stage surface. What follows — due, overdue, unapplied,
 * receipts — is a ledger at reading size rather than four more headlines: the
 * earlier composition set all four at hero size, and the eye had nowhere to
 * land. Tone repeats what a row's words already say; an amber ninety cents is
 * not a warning, so a warning is a mark beside the label, never a coloured
 * amount.
 *
 * Every amount arrived from the collections summary on this request. The
 * ageing track is drawn from the shares the server computed for each band;
 * nothing here divides one amount by another, and a balance the server gave
 * no shares for is aged in bands alone. Two currencies are never added: each
 * denomination gets its own stage and its own ledger, and the counts beneath
 * are project-wide because a count of accounts is not money.
 */
export function CollectionsPosition({
  summary,
  currencyCodeOf,
}: {
  summary: CollectionProjectSummary;
  currencyCodeOf: (id: string | null | undefined) => string | null;
}) {
  return (
    <div className="stack stack-tight">
      {summary.currencies.map((totals) => (
        <CurrencyPosition
          key={totals.currency_id}
          totals={totals}
          asOf={summary.as_of}
          code={currencyCodeOf(totals.currency_id)}
          titled={summary.currencies.length > 1}
        />
      ))}
      <StatStrip>
        <StatStripItem label="Accounts" value={summary.accounts} />
        <StatStripItem
          label="Overdue"
          value={summary.accounts_overdue}
          tone={summary.accounts_overdue > 0 ? "danger" : "neutral"}
        />
        <StatStripItem
          label="Disputed"
          value={summary.accounts_disputed}
          tone={summary.accounts_disputed > 0 ? "warning" : "neutral"}
        />
        <StatStripItem label="Cleared" value={summary.accounts_cleared} />
        <StatStripNote>As at {businessDate(summary.as_of)}</StatStripNote>
      </StatStrip>
    </div>
  );
}

/** One denomination's position. A project selling in two currencies has two. */
function CurrencyPosition({
  totals,
  asOf,
  code,
  titled,
}: {
  totals: CollectionCurrencyTotals;
  asOf: string;
  code: string | null;
  /** Named only when there is more than one, so a single currency is not labelled twice. */
  titled: boolean;
}) {
  const overdue = isPositive(totals.overdue_total);
  const unapplied = isPositive(totals.unapplied_cash);
  const bands = AGING_BUCKETS.filter((bucket) => totals.buckets[bucket] !== undefined);
  return (
    <div className="currency-block">
      {titled ? (
        <p className="currency-block-title">
          {code ?? "Unknown currency"}
          <span className="muted">
            · {totals.accounts} account{totals.accounts === 1 ? "" : "s"}
          </span>
        </p>
      ) : null}
      <div className="ledger-position">
        <div className="position-stage">
          <PositionFigure
            lead
            label="Outstanding"
            value={money(totals.outstanding_total, code)}
            note="Owed on active payment schedules"
          />
        </div>
        <Breakdown ledger>
          <BreakdownRow label="Due now" amount={money(totals.due_total, code)} />
          <BreakdownRow
            label="Overdue"
            note={`Past grace as at ${businessDate(asOf)}`}
            amount={money(totals.overdue_total, code)}
            tone={overdue ? "danger" : "neutral"}
            mark={overdue ? "danger" : undefined}
          />
          <BreakdownRow
            label="Unapplied cash"
            note="Received, not yet applied to an instalment"
            amount={money(totals.unapplied_cash, code)}
            mark={unapplied ? "warning" : undefined}
          />
          <BreakdownRow
            label="Confirmed receipts, lifetime"
            amount={money(totals.confirmed_receipts_total, code)}
          />
        </Breakdown>
      </div>
      <SectionHeader title="Ageing" actions={<span className="muted">Share of outstanding, as reported</span>} />
      <DistributionTrack
        label="Share of outstanding"
        segments={bands.map((bucket) => ({
          key: bucket,
          label: bucketLabel(bucket),
          share: totals.bucket_shares[bucket],
          heat: bucketHeatForAmount(bucket, totals.buckets[bucket]),
        }))}
      />
      <Distribution>
        {bands.map((bucket) => (
          <DistributionBand
            key={bucket}
            label={bucketLabel(bucket)}
            value={money(totals.buckets[bucket], code)}
            heat={bucketHeatForAmount(bucket, totals.buckets[bucket])}
            empty={!isPositive(totals.buckets[bucket])}
          />
        ))}
      </Distribution>
    </div>
  );
}
