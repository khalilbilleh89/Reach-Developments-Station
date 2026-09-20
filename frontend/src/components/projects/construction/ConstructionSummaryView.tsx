"use client";

import {
  Card,
  Disclosure,
  Metric,
  MetricGroup,
  Position,
  PositionFigure,
  PositionSupport,
  PositionSupportItem,
  SectionHeader,
} from "@/components/ui";
import type { ConstructionSummary } from "@/lib/api";
import { money } from "@/lib/format";


/** Signed commitments exclude tax; cash and invoice liabilities include tax. */
export function ConstructionSummaryView({
  summary,
}: {
  summary: ConstructionSummary;
}) {
  const code = summary.currency_code;
  const cost = summary.cost_control;
  const payable = summary.payable;
  const controls = summary.controls;

  return (
    <div className="stack">
      <Card tone="command" title="Contract costs" description="Excluding tax. Signed contracts plus approved additions and reductions.">
        <Position compact layout="split">
          <PositionFigure lead label="Revised contract value" value={money(cost.revised_commitment, code)} note="Original agreements plus approved changes" />
          <PositionFigure label="Original contract value" value={money(cost.original_commitment, code)} />
          <PositionFigure label="Variations & reductions" value={money(cost.approved_variation_delta, code)} note="Reductions lower the signed value" />
          <PositionFigure label="Certified to date" value={money(cost.certified_to_date, code)} note="Work formally certified" />
        </Position>
      </Card>

      <section className="record-section stack stack-tight">
        <SectionHeader
          title="Payable"
          description="Including tax, on a cash basis. Never compared with the figures above."
        />
        <Position compact>
          <PositionFigure
            label="Approved payable"
            value={money(payable.approved_invoice_payable, code)}
            note="Invoices a second person has approved"
          />
          <PositionFigure
            label="Disputed payable"
            value={money(payable.disputed_invoice_payable, code)}
            note="Under argument, and still owed"
          />
          <PositionFigure
            label="Standing outstanding"
            value={money(payable.invoice_outstanding, code)}
            note="Approved and disputed, less payments allocated to those invoices"
          />
          <PositionFigure
            label="Paid"
            value={money(payable.confirmed_paid, code)}
            note="Cash confirmed as gone"
          />
        </Position>
        <Disclosure title="Disputed payable treatment">
        <p className="footnote">
          A dispute blocks payment; it does not reduce the obligation.
          Outstanding therefore includes disputed invoices, because an amount
          that stopped being owed the moment somebody objected to it would make
          this a record of opinions.
        </p>
        </Disclosure>
        <PositionSupport>
          <PositionSupportItem
            label="Retention held back"
            value={money(payable.retention_outstanding, code)}
          />
          <PositionSupportItem
            label="Advance paid"
            value={money(payable.advance_paid, code)}
          />
          <PositionSupportItem
            label="Advance recovered"
            value={money(payable.advance_recovered, code)}
          />
          <PositionSupportItem
            label="Advance outstanding"
            value={money(payable.advance_outstanding, code)}
          />
        </PositionSupport>
      </section>

      <section className="record-section stack stack-tight">
        <SectionHeader
          title="What needs attention"
          description="Counts, not money. Each one is a thing somebody has to do."
        />
        <MetricGroup compact>
          <Metric
            label="Open variations"
            value={controls.open_variations}
            size="sm"
            note="Awaiting a decision"
            tone={controls.open_variations > 0 ? "warning" : "neutral"}
          />
          <Metric
            label="Need escalation"
            value={controls.escalated_variations}
            size="sm"
            note="Above the review amount"
            tone={controls.escalated_variations > 0 ? "warning" : "neutral"}
          />
          <Metric
            label="Late milestones"
            value={controls.late_milestones}
            size="sm"
            note="Past their planned date"
            tone={controls.late_milestones > 0 ? "danger" : "neutral"}
          />
          <Metric
            label="Reported, not certified"
            value={controls.achieved_uncertified_milestones}
            size="sm"
            note="Site says done; nothing has been triggered"
            tone={
              controls.achieved_uncertified_milestones > 0
                ? "warning"
                : "neutral"
            }
          />
          <Metric
            label="Overdue invoices"
            value={controls.overdue_approved_invoices}
            size="sm"
            note="Owed and past their due date"
            tone={controls.overdue_approved_invoices > 0 ? "danger" : "neutral"}
          />
        </MetricGroup>
      </section>
    </div>
  );
}
