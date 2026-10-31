"use client";

import type { PlanReconciliation } from "@/lib/api";
import { Badge, Banner, Metric, MetricGroup, StatusDot } from "@/components/ui";
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
      {/* A schedule that does not reconcile cannot be put forward: that is a
          condition to act on, pinned above the rows (design system G2). */}
      {ok ? (
        <p role="status">
          <StatusDot tone="success">Reconciled.</StatusDot>{" "}
          Principal, tax and fees reconcile to the selected schedule basis.
        </p>
      ) : (
        <Banner tone="warning">
          <strong>Does not reconcile.</strong> This schedule cannot be put forward yet.
          <ul className="reason-list">
            {reconciliation.blocking_reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </Banner>
      )}
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
