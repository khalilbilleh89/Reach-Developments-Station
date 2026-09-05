"use client";

import { Badge, Card, EmptyState, Loading, Notice, TableScroll } from "@/components/ui";
import type { Answer } from "@/lib/answer";
import type { CashflowMonthly as MonthlyReport, CashflowMonthlyPosition } from "@/lib/api";
import { cashflowCsvHref } from "@/lib/api";
import { businessDate, isPositive, money } from "@/lib/format";

import { monthBasisLabel, monthBasisNote, monthBasisTone } from "./labels";

/**
 * The cash bridge, month by month.
 *
 * Three customer series are shown and never merged, because they are three
 * different truths: what the buyers' schedules say becomes **due**, what
 * Finance **expects** to collect, and what actually **arrived**. Collapsing any
 * two produces a table that looks complete and answers the wrong question.
 *
 * The basis column has three values and not two. The month a report is taken in
 * is part spent and part still expected — labelling it "Actual" presents a part
 * month as a finished one, and a project read on the third of the month would
 * show a funding cliff that disappears on the fourth.
 *
 * Nothing on this screen is added up. Every column, including the closing
 * balances and the funding gap, arrives from `GET /cashflow/monthly`.
 */
export function CashflowMonthly({
  projectId,
  answer,
  asOf,
  onOpenMonth,
}: {
  projectId: string;
  answer: Answer<MonthlyReport>;
  asOf: string | null;
  onOpenMonth: (month: string) => void;
}) {
  if (answer.status === "loading") {
    return <Loading label="Loading the monthly cash bridge" shape="rows" />;
  }
  if (answer.status === "denied") {
    return <Notice tone="info">The monthly cash bridge is not available to your role.</Notice>;
  }
  if (answer.status === "failed") {
    return <Notice tone="error">{answer.message}</Notice>;
  }
  if (answer.status === "off") return null;

  const report = answer.data;
  const currency = report.basis.currency_code;

  return (
    <Card
      title="Monthly cashflow"
      description="Opening cash, what moves, and where the month closes — on the actual, forecast or blended basis each month is on."
      actions={
        <a
          className="button"
          href={cashflowCsvHref(projectId, "monthly", { asOf: asOf ?? undefined })}
        >
          Export CSV
        </a>
      }
    >
      {report.months.length === 0 ? (
        <EmptyState
          title="No months to show"
          hint="A cashflow forecast in force gives this bridge its horizon. Without one, only months containing real transactions appear."
        />
      ) : (
        <>
          <TableScroll label="Monthly cash bridge" fixedFirst compact>
            <thead>
              <tr>
                <th scope="col">Month</th>
                <th scope="col">Basis</th>
                <th scope="col" className="num">Opening cash</th>
                <th scope="col" className="num">Customer due</th>
                <th scope="col" className="num">Customer received</th>
                <th scope="col" className="num">Customer expected</th>
                <th scope="col" className="num">Refunds</th>
                <th scope="col" className="num">Financing in (actual)</th>
                <th scope="col" className="num">Financing in (expected)</th>
                <th scope="col" className="num">Construction paid</th>
                <th scope="col" className="num">Construction expected</th>
                <th scope="col" className="num">Development paid</th>
                <th scope="col" className="num">Development expected</th>
                <th scope="col" className="num">Financing out (actual)</th>
                <th scope="col" className="num">Financing out (expected)</th>
                <th scope="col" className="num">Total in</th>
                <th scope="col" className="num">Total out</th>
                <th scope="col" className="num">Net</th>
                <th scope="col" className="num">Closing cash</th>
                <th scope="col" className="num">Closing restricted</th>
                <th scope="col" className="num">Closing usable</th>
                <th scope="col" className="num">Funding gap</th>
              </tr>
            </thead>
            <tbody>
              {report.months.map((row) => (
                <MonthRow
                  key={row.period_month}
                  row={row}
                  currency={currency}
                  onOpen={() => onOpenMonth(row.period_month)}
                />
              ))}
            </tbody>
          </TableScroll>
          <BasisLegend months={report.months} />
          <p className="footnote">
            <strong>Customer due</strong> is what the governing buyer schedules
            say falls due; <strong>customer expected</strong> is what Finance
            expects to collect, already reduced by cash that has arrived;{" "}
            <strong>customer received</strong> is what actually arrived. They are
            three separate facts and are never added together.
          </p>
        </>
      )}
    </Card>
  );
}

function MonthRow({
  row,
  currency,
  onOpen,
}: {
  row: CashflowMonthlyPosition;
  currency: string | null;
  onOpen: () => void;
}) {
  const short = isPositive(row.funding_gap);
  return (
    <tr>
      <th scope="row">
        <button type="button" className="button-link" onClick={onOpen}>
          {businessDate(row.period_month)}
        </button>
      </th>
      <td>
        <Badge tone={monthBasisTone(row.basis)}>{monthBasisLabel(row.basis)}</Badge>
      </td>
      <td className="num">{money(row.opening_total_cash, currency)}</td>
      <td className="num">{money(row.customer_scheduled_due, currency)}</td>
      <td className="num">{money(row.customer_actual_receipts, currency)}</td>
      <td className="num">{money(row.customer_forecast_receipts, currency)}</td>
      <td className="num">{money(row.customer_refunds, currency)}</td>
      <td className="num">{money(row.financing_actual_inflows, currency)}</td>
      <td className="num">{money(row.financing_forecast_inflows, currency)}</td>
      <td className="num">{money(row.construction_actual_payments, currency)}</td>
      <td className="num">{money(row.construction_forecast_payments, currency)}</td>
      <td className="num">{money(row.development_actual_outflows, currency)}</td>
      <td className="num">{money(row.development_forecast_outflows, currency)}</td>
      <td className="num">{money(row.financing_actual_outflows, currency)}</td>
      <td className="num">{money(row.financing_forecast_outflows, currency)}</td>
      <td className="num">{money(row.total_inflows, currency)}</td>
      <td className="num">{money(row.total_outflows, currency)}</td>
      <td className="num">{money(row.net_cashflow, currency)}</td>
      <td className="num">{money(row.closing_total_cash, currency)}</td>
      <td className="num">{money(row.closing_restricted_cash, currency)}</td>
      <td className="num">{money(row.closing_unrestricted_cash, currency)}</td>
      <td className="num">
        {short ? <strong>{money(row.funding_gap, currency)}</strong> : "—"}
      </td>
    </tr>
  );
}

/**
 * What each basis in this table means, in words under it.
 *
 * Under the table rather than in a tooltip on the badge: a `title` attribute is
 * invisible to a keyboard, to a touch screen and to most screen readers, and
 * the difference between a finished month and a part-spent one is exactly the
 * thing a reader must not have to hover to discover.
 */
function BasisLegend({ months }: { months: CashflowMonthlyPosition[] }) {
  const present = Array.from(new Set(months.map((row) => row.basis)));
  if (present.length === 0) return null;
  return (
    <dl className="footnote">
      {present.map((basis) => (
        <div key={basis}>
          <dt>
            <strong>{monthBasisLabel(basis)}</strong>
          </dt>
          <dd>{monthBasisNote(basis)}</dd>
        </div>
      ))}
    </dl>
  );
}
