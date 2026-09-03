"use client";

import type { PlanReconciliation } from "@/lib/api";
import { Badge, Metric, MetricGroup } from "@/components/ui";
import { useCurrencyCode } from "@/lib/currency";
import { money, percent } from "@/lib/format";

/**
 * What the schedule adds up to, against what it must cover.
 *
 * Every figure here came from the server's own reconciliation. Nothing on this
 * screen sums a column: a second implementation of the total would eventually
 * disagree with the one the activation gate uses, and the disagreement would be
 * discovered by an operator who cannot submit a plan that looks correct.
 *
 * When it does not reconcile, the reasons are the server's words — "Principal
 * is short by 5,000.00" — because an operator told the plan is invalid has to
 * find the discrepancy across forty rows themselves.
 */
export function ReconciliationStrip({
  reconciliation,
  currencyId,
}: {
  reconciliation: PlanReconciliation;
  currencyId: string;
}) {
  const currencyCodeOf = useCurrencyCode();
  const code = currencyCodeOf(currencyId);
  const ok = reconciliation.is_reconciled;

  return (
    <>
      <MetricGroup compact>
        <Metric
          label="Principal scheduled"
          value={money(reconciliation.scheduled_principal_total, code)}
          note={`of ${money(reconciliation.contract_value_covered, code)}`}
          size="sm"
        />
        <Metric
          label="Share scheduled"
          value={percent(reconciliation.scheduled_fraction_total)}
          note="Must total 100%"
          size="sm"
        />
        <Metric
          label="Tax"
          value={money(reconciliation.scheduled_tax_total, code)}
          note={`of ${money(reconciliation.tax_total_snapshot, code)}`}
          size="sm"
        />
        <Metric
          label="Buyer fees"
          value={money(reconciliation.scheduled_fee_total, code)}
          note={`of ${money(reconciliation.buyer_fee_total_snapshot, code)}`}
          size="sm"
        />
        <Metric
          label="Buyer total"
          value={money(reconciliation.scheduled_buyer_total, code)}
          note={`of ${money(reconciliation.total_buyer_payable_snapshot, code)}`}
          size="sm"
        />
        <Metric label="Instalments" value={reconciliation.installment_count} size="sm" />
      </MetricGroup>
      <div className={ok ? "reconcile reconcile-ok" : "reconcile reconcile-fail"} role="status">
        <span className="reconcile-title">{ok ? "Reconciled." : "Does not reconcile."}</span>
        <span>
          {ok
            ? "The schedule covers the contract exactly."
            : "This schedule cannot be put forward yet."}
        </span>
        {ok ? null : (
          <ul className="reason-list">
            {reconciliation.blocking_reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        )}
      </div>
    </>
  );
}

/** The compact form, for a register row or a summary card. */
export function ReconciliationBadge({ reconciled }: { reconciled: boolean }) {
  return reconciled ? (
    <Badge tone="success">Reconciled</Badge>
  ) : (
    <Badge tone="warning">Does not reconcile</Badge>
  );
}
