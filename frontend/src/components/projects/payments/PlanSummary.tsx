"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, paymentPlans } from "@/lib/api";
import type { PaymentPlanDetail } from "@/lib/api";
import { Badge, Button, EmptyState, Notice, InlineMeta, InlineMetaItem, KeyValue, KeyValueGrid, Loading } from "@/components/ui";
import { useCurrencyCode } from "@/lib/currency";
import { businessDate, money } from "@/lib/format";
import { ReconciliationBadge } from "@/components/projects/payments/ReconciliationStrip";
import { versionLabel, versionTone } from "@/components/projects/payments/labels";

/**
 * A sale's payment plan, in as much depth as a deal file or Unit 360 needs.
 *
 * The summary opens the same builder used by the Payment plans section. What is
 * shown is what somebody looking at the deal actually asks — is there a plan,
 * which version governs, how many instalments, what is next, and how many are
 * still waiting on something.
 *
 * What it reports is the schedule that actually governs the sale, not the one
 * somebody happens to be drafting. Those are the same version most of the
 * time and emphatically not during a revision, which can run for weeks: a
 * deal file that swapped in a half-written draft's figures the moment
 * Collections opened one would be telling the reader the buyer owes something
 * nobody has agreed to. Where no version governs yet, the plan in preparation
 * is shown and labelled as such.
 *
 * The next dates come from the server, already filtered to what is still to
 * come. Sorting the dates here and taking the first would surface a date from
 * last March under a heading like "next", which reads as arrears. Collections
 * separately supplies the receipt journal, collected amount and outstanding.
 */
export function PlanSummary({
  projectId,
  saleId,
  compact,
  roles,
  saleStatus,
  onOpenPlan,
}: {
  projectId: string;
  saleId: string;
  /** Unit 360 shows fewer facts than the deal file. */
  compact?: boolean;
  roles?: Set<string>;
  saleStatus?: string;
  onOpenPlan?: (planId: string) => void;
}) {
  const [detail, setDetail] = useState<PaymentPlanDetail | null | "none">(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const currencyCodeOf = useCurrencyCode();

  const load = useCallback(async () => {
    try {
      const body = await paymentPlans.forSale(projectId, saleId);
      setDetail(body ?? "none");
      setProblem(null);
    } catch (caught) {
      setProblem(caught instanceof ApiError && caught.isForbidden
        ? "Payment plans are not available to your role."
        : caught instanceof ApiError ? caught.message : "Could not load the payment plan.");
    }
  }, [projectId, saleId]);

  useEffect(() => {
    void (async () => {
      await load();
    })();
  }, [load]);

  if (problem && detail === null) return <Notice tone="error">{problem}</Notice>;
  if (detail === null) return <Loading label="Loading the payment plan…" shape="rows" rows={3} />;
  if (detail === "none") {
    return (
      <>
        {problem ? <Notice tone="error">{problem}</Notice> : null}
        <EmptyState title="No SPA payment schedule yet" hint="Collections prepares the instalments agreed in the SPA, then submits the schedule for separate approval." />
        {onOpenPlan && roles?.has("collections") && ["signature_pending", "active"].includes(saleStatus ?? "") ? (
          <Button variant="primary" disabled={creating} onClick={async () => {
            setCreating(true);
            setProblem(null);
            try {
              const created = await paymentPlans.create(projectId, { sale_contract_id: saleId, name: "SPA payment schedule" });
              onOpenPlan(created.plan.id);
            } catch (caught) {
              setProblem(caught instanceof ApiError ? caught.message : "Could not create the payment schedule.");
            } finally { setCreating(false); }
          }}>Create SPA payment schedule</Button>
        ) : null}
      </>
    );
  }

  // The governing schedule if there is one; otherwise the one being prepared,
  // which is then labelled so nobody reads it as binding.
  const shown = detail.active ?? detail.current;
  const governs = detail.active !== null;
  const revision =
    detail.active && detail.current && detail.current.version.id !== detail.active.version.id
      ? detail.current.version
      : null;
  const version = shown?.version ?? null;
  const reconciliation = shown?.reconciliation ?? null;
  const installments = shown?.installments ?? [];
  const code = currencyCodeOf(detail.currency_id);
  const awaiting = installments.filter((row) => row.trigger_status === "awaiting_trigger").length;

  return (
    <>
      {onOpenPlan ? <Button onClick={() => onOpenPlan(detail.plan.id)}>Open SPA payment schedule</Button> : null}
      <InlineMeta>
        <InlineMetaItem label="Plan">
          <span className="mono">{detail.plan.plan_number}</span>
        </InlineMetaItem>
        {version ? (
          <InlineMetaItem label={`v${version.version_number}`}>
            <Badge tone={versionTone(version.status)}>{versionLabel(version.status)}</Badge>{" "}
            {governs ? "Governing schedule" : "Not yet governing"}
          </InlineMetaItem>
        ) : null}
        {revision ? (
          <InlineMetaItem label="In preparation">
            v{revision.version_number}{" "}
            <Badge tone={versionTone(revision.status)}>{versionLabel(revision.status)}</Badge>
          </InlineMetaItem>
        ) : null}
        {reconciliation ? (
          <InlineMetaItem label="Reconciliation">
            <ReconciliationBadge reconciled={reconciliation.is_reconciled} />
          </InlineMetaItem>
        ) : null}
      </InlineMeta>
      <KeyValueGrid columns={3}>
        <KeyValue
          label="Scheduled principal"
          mono
          value={money(reconciliation?.scheduled_principal_total ?? null, code)}
        />
        <KeyValue label="Instalments" value={reconciliation?.installment_count ?? 0} />
        <KeyValue
          label="Next scheduled"
          mono
          value={
            shown?.next_scheduled_date
              ? businessDate(shown.next_scheduled_date)
              : "No future date"
          }
        />
        {compact ? null : (
          <>
            <KeyValue
              label="Next forecast"
              mono
              value={
                shown?.next_forecast_date
                  ? businessDate(shown.next_forecast_date)
                  : "No future date"
              }
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
        {governs
          ? "These are the terms currently governing the sale. Receipts and allocations are recorded in the receipt journal."
          : "This plan is still being prepared and does not govern the sale yet. Scheduled, not collected."}
        {revision
          ? ` Revision v${revision.version_number} is being prepared and does not govern anything until it is activated.`
          : ""}
      </p>
    </>
  );
}
