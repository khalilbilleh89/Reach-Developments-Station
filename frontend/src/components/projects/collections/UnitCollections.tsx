"use client";

import type { CollectionSaleSummary } from "@/lib/api";
import type { Answer } from "@/lib/answer";
import {
  Badge,
  Button,
  EmptyState,
  KeyValue,
  KeyValueGrid,
  Loading,
  Metric,
  MetricGroup,
  Notice,
  SectionHeader,
} from "@/components/ui";
import { useCurrencyCode } from "@/lib/currency";
import { businessDate, isPositive, money } from "@/lib/format";

import { unitCollectionLabel, unitCollectionTone } from "./labels";

/**
 * The collection dimension on Unit 360, and the figures behind the badge.
 *
 * Unit 360 has shown a `collection_status` since PR-MVP-03 with nothing to
 * substantiate it. This is what it means: the cash confirmed against this
 * unit's contract, how much of it has been applied, what is still outstanding
 * and how much of that is overdue.
 *
 * Deliberately a position and a link, not a second collections workspace.
 * Every figure comes from the sale's own summary endpoint — the same function
 * the register and the account screen call — so a reader who checks this
 * against the Collections section finds the same numbers rather than a second
 * opinion. The request is made once, by the unit file, and only on behalf of
 * a role the server answers; this component only lays the answer out.
 */
export function UnitCollections({
  answer,
  onOpenCollections,
}: {
  answer: Answer<CollectionSaleSummary>;
  onOpenCollections?: () => void;
}) {
  const currencyCodeOf = useCurrencyCode();

  if (answer.status === "off") {
    // Never requested: either nothing is contracted on the unit yet, or the
    // reader's role is not one the server answers, so the unit file did not
    // ask. This component cannot tell the two apart and does not pretend to.
    return (
      <EmptyState
        title="No collections position to show"
        hint="A collections account exists once a contract is signed on the unit, and its figures are shown only to roles that may read collections."
      />
    );
  }
  if (answer.status === "loading") {
    return <Loading label="Loading the collections position" shape="metrics" />;
  }
  if (answer.status === "denied") {
    return (
      <EmptyState
        title="Not available to your role"
        hint="The cash position of a contract belongs to Collections, Finance and audit."
      />
    );
  }
  if (answer.status === "failed") {
    return <Notice tone="error">{answer.message}</Notice>;
  }

  const summary = answer.data;
  const code = currencyCodeOf(summary.currency_id);

  return (
    <>
      <section>
        <SectionHeader
          title="Position"
          description={`As at ${businessDate(summary.as_of)}.`}
          actions={
            <>
              <Badge tone={unitCollectionTone(summary.derived_collection_status)}>
                {unitCollectionLabel(summary.derived_collection_status)}
              </Badge>
              {onOpenCollections ? (
                <Button small onClick={onOpenCollections}>
                  Collections account
                </Button>
              ) : null}
            </>
          }
        />
        <MetricGroup>
          <Metric label="Scheduled" value={money(summary.scheduled_total, code)} size="sm" />
          <Metric
            label="Collected"
            value={money(summary.allocated_total, code)}
            note="Confirmed and applied"
          />
          <Metric label="Outstanding" value={money(summary.outstanding_total, code)} />
          <Metric
            label="Overdue"
            value={money(summary.overdue_total, code)}
            tone={summary.oldest_overdue_days > 0 ? "danger" : "neutral"}
            note={
              summary.oldest_overdue_days > 0
                ? `Oldest ${summary.oldest_overdue_days} days`
                : "Nothing past grace"
            }
          />
          <Metric
            label="Unapplied cash"
            value={money(summary.unapplied_cash, code)}
            note="Received, not yet applied"
            size="sm"
          />
        </MetricGroup>
        {isPositive(summary.unapplied_cash) ? (
          <p className="footnote">
            Confirmed cash on this account has not been applied to an instalment, so it is not
            reducing the outstanding balance.
          </p>
        ) : null}
        {summary.open_disputes > 0 ? (
          <Notice tone="warning">
            {summary.open_disputes} instalment
            {summary.open_disputes === 1 ? " is" : "s are"} disputed. The balance is unchanged and
            still ageing.
          </Notice>
        ) : null}
      </section>

      <section>
        <SectionHeader title="Instalments" />
        <KeyValueGrid columns={4}>
          <KeyValue label="Scheduled" mono value={String(summary.installments_total)} />
          <KeyValue label="Paid" mono value={String(summary.installments_paid)} />
          <KeyValue label="Partly paid" mono value={String(summary.installments_partial)} />
          <KeyValue label="Overdue" mono value={String(summary.installments_overdue)} />
          <KeyValue
            label="Awaiting trigger"
            mono
            value={String(summary.installments_awaiting_trigger)}
          />
          <KeyValue label="Active waivers" mono value={String(summary.active_waivers)} />
          <KeyValue label="Open disputes" mono value={String(summary.open_disputes)} />
          <KeyValue label="Next action" mono value={businessDate(summary.next_action_date)} />
        </KeyValueGrid>
        <p className="footnote">
          Receipts, allocations, disputes and waivers are recorded on the collections account in the
          Collections section of the project.
        </p>
      </section>
    </>
  );
}
