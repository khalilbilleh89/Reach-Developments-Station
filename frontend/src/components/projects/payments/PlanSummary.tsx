"use client";

import { useCallback, useEffect, useState } from "react";

import { paymentPlans } from "@/lib/api";
import type { PaymentPlanDetail } from "@/lib/api";
import { Badge, EmptyState, KeyValue, KeyValueGrid, Loading } from "@/components/ui";
import { useCurrencyCode } from "@/lib/currency";
import { businessDate, money } from "@/lib/format";
import { ReconciliationBadge } from "@/components/projects/payments/ReconciliationStrip";
import { versionLabel, versionTone } from "@/components/projects/payments/labels";

/**
 * A sale's payment plan, in as much depth as a deal file or Unit 360 needs.
 *
 * Compact by design: the whole builder belongs on the Payment plans section,
 * and duplicating it here would give two places to edit one schedule. What is
 * shown is what somebody looking at the deal actually asks — is there a plan,
 * which version governs, how many instalments, what is next, and how many are
 * still waiting on something.
 *
 * No collected or outstanding figure appears, because none exists. PR-MVP-07
 * will add that here, and until it does the absence is the honest answer.
 */
export function PlanSummary({
  projectId,
  saleId,
  compact,
}: {
  projectId: string;
  saleId: string;
  /** Unit 360 shows fewer facts than the deal file. */
  compact?: boolean;
}) {
  const [detail, setDetail] = useState<PaymentPlanDetail | null | "none">(null);
  const [denied, setDenied] = useState(false);
  const currencyCodeOf = useCurrencyCode();

  const load = useCallback(async () => {
    try {
      const body = await paymentPlans.forSale(projectId, saleId);
      setDetail(body ?? "none");
    } catch {
      // A reader who may see the deal is not always entitled to its schedule,
      // and a refusal there must not blank the deal they can see.
      setDenied(true);
    }
  }, [projectId, saleId]);

  useEffect(() => {
    void (async () => {
      await load();
    })();
  }, [load]);

  if (denied) return <p className="subtle">Not available to your role.</p>;
  if (detail === null) return <Loading label="Loading the payment plan…" />;
  if (detail === "none") {
    return (
      <EmptyState
        title="No payment plan yet"
        hint="Collections schedules what the buyer agreed to pay, on the project's Payment plans section."
      />
    );
  }

  const version = detail.current?.version ?? null;
  const reconciliation = detail.current?.reconciliation ?? null;
  const installments = detail.current?.installments ?? [];
  const code = currencyCodeOf(detail.currency_id);
  const nextActual = installments
    .map((row) => row.actual_due_date)
    .filter((value): value is string => Boolean(value))
    .sort()[0];
  const nextForecast = installments
    .map((row) => row.forecast_due_date)
    .filter((value): value is string => Boolean(value))
    .sort()[0];
  const awaiting = installments.filter((row) => row.trigger_status === "awaiting_trigger").length;

  return (
    <>
      <ul className="chip-list">
        <li className="chip">
          <span className="chip-label">Plan</span>
          <strong className="mono">{detail.plan.plan_number}</strong>
        </li>
        {version ? (
          <li className="chip">
            <span className="chip-label">v{version.version_number}</span>
            <Badge tone={versionTone(version.status)}>{versionLabel(version.status)}</Badge>
          </li>
        ) : null}
        {reconciliation ? (
          <li>
            <ReconciliationBadge reconciled={reconciliation.is_reconciled} />
          </li>
        ) : null}
      </ul>
      <KeyValueGrid columns={3}>
        <KeyValue
          label="Scheduled principal"
          mono
          value={money(reconciliation?.scheduled_principal_total ?? null, code)}
        />
        <KeyValue label="Instalments" value={reconciliation?.installment_count ?? 0} />
        <KeyValue
          label="Next contractual date"
          mono
          value={businessDate(nextActual ?? null)}
        />
        {compact ? null : (
          <>
            <KeyValue
              label="Next forecast date"
              mono
              value={businessDate(nextForecast ?? null)}
            />
            <KeyValue
              label="Buyer total scheduled"
              mono
              value={money(reconciliation?.scheduled_buyer_total ?? null, code)}
            />
            <KeyValue label="Takes effect" mono value={businessDate(version?.effective_date)} />
          </>
        )}
        <KeyValue
          label="Awaiting a trigger"
          value={awaiting === 0 ? "None" : `${awaiting} instalment(s)`}
        />
      </KeyValueGrid>
      <p className="footnote">
        Scheduled, not collected. What has actually been received is recorded from PR-MVP-07
        onwards.
      </p>
    </>
  );
}
