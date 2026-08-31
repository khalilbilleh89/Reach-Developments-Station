"use client";

import type { PlanReconciliation } from "@/lib/api";
import { Badge, Notice, Stat, StatRow } from "@/components/ui";
import { useCurrencyCode } from "@/lib/currency";
import { money } from "@/lib/format";

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
      <StatRow>
        <Stat
          label="Principal scheduled"
          value={money(reconciliation.scheduled_principal_total, code)}
          note={`of ${money(reconciliation.contract_value_covered, code)}`}
        />
        <Stat
          label="Percentage"
          value={reconciliation.scheduled_fraction_total}
          note="must total 1.000000"
          small
        />
        <Stat
          label="Tax"
          value={money(reconciliation.scheduled_tax_total, code)}
          note={`of ${money(reconciliation.tax_total_snapshot, code)}`}
          small
        />
        <Stat
          label="Buyer fees"
          value={money(reconciliation.scheduled_fee_total, code)}
          note={`of ${money(reconciliation.buyer_fee_total_snapshot, code)}`}
          small
        />
        <Stat
          label="Buyer total"
          value={money(reconciliation.scheduled_buyer_total, code)}
          note={`of ${money(reconciliation.total_buyer_payable_snapshot, code)}`}
        />
        <Stat
          label="Instalments"
          value={reconciliation.installment_count}
          note={ok ? "Reconciled" : "Does not reconcile"}
          small
        />
      </StatRow>
      {ok ? (
        <Notice tone="success">
          <strong>Reconciled.</strong> The schedule covers the contract exactly.
        </Notice>
      ) : (
        <Notice tone="warning">
          <strong>This schedule cannot be put forward yet.</strong>
          <ul className="reason-list">
            {reconciliation.blocking_reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </Notice>
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
