"use client";

import { useCallback, useEffect, useState } from "react";

import { paymentPlans } from "@/lib/api";
import type { PaymentPlanDetail } from "@/lib/api";
import { Badge, EmptyState, InlineMeta, InlineMetaItem, KeyValue, KeyValueGrid, Loading } from "@/components/ui";
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
 * last March under a heading like "next", which reads as arrears — and
 * PR-MVP-06 cannot know whether anything is in arrears.
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
  if (detail === null) return <Loading label="Loading the payment plan…" shape="rows" rows={3} />;
  if (detail === "none") {
    return (
      <EmptyState
        title="No payment plan yet"
        hint="Collections schedules what the buyer agreed to pay, on the project's Payment plans section."
      />
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
          ? "Scheduled, not collected. These are the terms currently governing the sale; what has actually been received is recorded from PR-MVP-07 onwards."
          : "This plan is still being prepared and does not govern the sale yet. Scheduled, not collected."}
        {revision
          ? ` Revision v${revision.version_number} is being prepared and does not govern anything until it is activated.`
          : ""}
      </p>
    </>
  );
}
