import type { CollectionSaleSummary } from "@/lib/api";
import { Metric, MetricGroup, ProgressRing } from "@/components/ui";
import { useCurrencyCode } from "@/lib/currency";
import { businessDate, money } from "@/lib/format";

/** Both the numerator and percentage are the dated ledger's server figures. */
export function CollectionProgress({ summary }: { summary: CollectionSaleSummary }) {
  const currencyCodeOf = useCurrencyCode();
  const code = currencyCodeOf(summary.currency_id);
  return (
    <section>
      <MetricGroup compact>
        <Metric label="Total SPA payable" value={money(summary.spa_total_payable, code)} note="Including tax and buyer fees" />
        <Metric label="Confirmed receipts" value={money(summary.confirmed_receipts_total, code)} note="Includes unapplied cash" />
        {summary.collected_percentage === null
          ? <Metric label="Collected of SPA" value="Not applicable" note="Confirmed receipts ÷ total SPA payable" />
          : <ProgressRing focus percent={summary.collected_percentage} label="Collected of SPA" note="Confirmed receipts ÷ total SPA payable" />}
      </MetricGroup>
      <p className="footnote">As at {businessDate(summary.as_of)}. Recorded receipts count after Finance confirms them. Refunds are shown separately; this percentage does not establish settlement or clearance.</p>
    </section>
  );
}
