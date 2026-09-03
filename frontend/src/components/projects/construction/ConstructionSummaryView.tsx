"use client";

import {
  Metric,
  MetricGroup,
  Position,
  PositionFigure,
  PositionSupport,
  PositionSupportItem,
  SectionHeader,
} from "@/components/ui";
import type { ConstructionSummary } from "@/lib/api";
import { businessDate, money } from "@/lib/format";

import { varianceNote, varianceTone } from "./labels";

/**
 * The project's construction position: two bases, never one blended figure.
 *
 * The whole design of this screen is the separation between them, and it is
 * why they are two compositions with two headings rather than one strip of
 * eleven numbers.
 *
 * **Cost control is stated excluding tax.** What was authorised, what has been
 * committed, what has been certified and what it is now forecast to finish at.
 * Tax is recoverable in most of the jurisdictions this product serves, so a
 * cost figure that included it would overstate what the building cost.
 *
 * **Payable is stated including tax, on a cash basis.** What is owed, what has
 * actually left the bank, and what is held back. That is the number a treasury
 * function works from, and it necessarily includes the tax the company will
 * actually pay out.
 *
 * A screen that put "certified 4,200,000" next to "paid 3,900,000" without
 * saying that one excludes tax and the other includes it would invite a
 * subtraction whose answer means nothing. So the two never share a row, never
 * share a heading, and each says its basis in words above the figures.
 *
 * Every value arrived on this request. Nothing here is summed, netted or
 * projected in the browser — including the variance, whose sign convention
 * (**positive is over budget**) is the server's and is never re-derived here.
 */
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
      <section className="stack stack-tight">
        <SectionHeader
          title="Cost control"
          description={
            summary.budget_version_number === null
              ? "Excluding tax. No budget is in force, so there is nothing authorised to measure against."
              : `Excluding tax, against budget version ${summary.budget_version_number}.`
          }
        />
        <Position>
          <PositionFigure
            label="Control budget"
            value={money(cost.control_budget, code)}
            note="Approved budget plus contingency"
          />
          <PositionFigure
            label="Revised commitment"
            value={money(cost.revised_commitment, code)}
            note="Signed contracts and approved variations"
          />
          <PositionFigure
            label="Certified to date"
            value={money(cost.certified_to_date, code)}
            note="Work formally certified, as at today"
          />
          <PositionFigure
            lead
            label="Variance at completion"
            value={money(cost.variance_at_completion, code)}
            tone={varianceTone(cost.variance_at_completion)}
            note={varianceNote(cost.variance_at_completion)}
          />
        </Position>
        {summary.forecast_version_number === null ? null : (
          <p className="footnote">
            Certified to date is today&apos;s figure. The estimate at completion
            is not: it is the work certified by the forecast&apos;s own cutoff
            plus what that forecast said was still to come, and it stays on that
            basis until a new forecast is activated. Certifying work after the
            cutoff therefore moves the first figure and leaves the second alone,
            which is the only way the two avoid counting the same work twice.
          </p>
        )}
        <PositionSupport>
          <PositionSupportItem
            label="Original baseline"
            value={money(cost.original_baseline, code)}
          />
          <PositionSupportItem
            label="Approved budget"
            value={money(cost.current_approved_budget, code)}
          />
          <PositionSupportItem
            label="Contingency"
            value={money(cost.approved_contingency, code)}
          />
          <PositionSupportItem
            label="Original commitment"
            value={money(cost.original_commitment, code)}
          />
          <PositionSupportItem
            label="Approved variations"
            value={money(cost.approved_variation_delta, code)}
          />
          <PositionSupportItem
            label="Certified at forecast cutoff"
            value={money(cost.forecast_certified_as_of, code)}
          />
          <PositionSupportItem
            label="Forecast remaining"
            value={money(cost.forecast_remaining, code)}
          />
          <PositionSupportItem
            label="Estimate at completion"
            value={money(cost.estimate_at_completion, code)}
          />
          <PositionSupportItem
            label="Forecast"
            value={
              summary.forecast_version_number === null
                ? "None in force"
                : `Version ${summary.forecast_version_number}, as at ${businessDate(summary.forecast_as_of)}`
            }
          />
        </PositionSupport>
      </section>

      <section className="stack stack-tight">
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
            note="Approved and disputed, less cash confirmed as gone"
          />
          <PositionFigure
            label="Paid"
            value={money(payable.confirmed_paid, code)}
            note="Cash confirmed as gone"
          />
        </Position>
        <p className="footnote">
          A dispute blocks payment; it does not reduce the obligation.
          Outstanding therefore includes disputed invoices, because an amount
          that stopped being owed the moment somebody objected to it would make
          this a record of opinions.
        </p>
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

      <section className="stack stack-tight">
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
            label="Over budget"
            value={controls.over_budget_cost_codes}
            size="sm"
            note="Cost codes committed past their limit"
            tone={controls.over_budget_cost_codes > 0 ? "danger" : "neutral"}
          />
          <Metric
            label="Forecast under commitment"
            value={controls.forecast_below_commitment_cost_codes}
            size="sm"
            note="Forecast to spend less than is signed"
            tone={
              controls.forecast_below_commitment_cost_codes > 0
                ? "warning"
                : "neutral"
            }
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
