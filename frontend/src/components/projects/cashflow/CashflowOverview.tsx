"use client";

import {
  Badge,
  Banner,
  Button,
  Card,
  KeyValue,
  KeyValueGrid,
  Position,
  PositionFigure,
  PositionSupport,
  PositionSupportItem,
  SectionHeader,
  SourceNote,
  StatStrip,
  StatStripNote,
  SubPanel,
  TableScroll,
  Tooltip,
} from "@/components/ui";
import type { CashflowSummary } from "@/lib/api";
import { businessDate, isPositive, money, percent } from "@/lib/format";

import { irrReasonLabel } from "./labels";

/**
 * Where the project's cash stands, and when it runs short.
 *
 * The screen is built around one figure: **unrestricted cash**. Total cash
 * includes escrowed buyer money that cannot pay a contractor, and a developer
 * reading a healthy total while unable to meet a certificate has been told
 * something true and useless. Total and restricted are stated beside it, in
 * words, so nobody has to subtract two numbers on a screen to learn what the
 * company can actually spend.
 *
 * Nothing here is computed. Every figure arrives from
 * `GET /cashflow/summary` — the position, the funding windows, the trough, the
 * NPV and the equity IRR — because a cash position recalculated in a browser is
 * a position that can disagree with the one Finance will act on.
 */
export function CashflowOverview({ summary, onOpenForecast }: { summary: CashflowSummary; onOpenForecast: () => void }) {
  const { basis, position, peak_deficit: peak, returns } = summary;
  const currency = basis.currency_code;
  const shortOfCash = isPositive(peak.peak_funding_deficit);

  return (
    <div className="stack">
      <Card
        tone="command"
        title="Cash position"
        description="What the project holds, and how much of it can be spent."
        actions={
          <SourceNote
            coverage="available"
            label="Spendable cash basis"
            method="Unrestricted cash is the figure to act on: it is what the project can pay a contractor with today. Restricted cash is buyer money held in escrow against the receipts it came from — it is on the balance sheet and cannot be spent."
          />
        }
      >
        <Position layout="split">
          <PositionFigure
            lead
            label="Unrestricted cash"
            value={money(position.unrestricted_cash, currency)}
            note="Spendable today"
            tone={isPositive(position.unrestricted_cash) ? "neutral" : "danger"}
          />
          <PositionFigure
            label="Total cash"
            value={money(position.total_cash, currency)}
            note="In the bank"
          />
          <PositionFigure
            label="Restricted cash"
            value={money(position.restricted_cash, currency)}
            note="Held in escrow"
          />
        </Position>
        <PositionSupport>
          <PositionSupportItem label="As at" value={businessDate(basis.as_of_date)} />
          <PositionSupportItem label="Currency" value={currency ?? "—"} />
          <PositionSupportItem
            label="Forecast in force"
            value={
              summary.has_active_forecast && basis.forecast_version_number !== null
                ? `Version ${basis.forecast_version_number}`
                : "None"
            }
          />
          <PositionSupportItem
            label="Forecast taken as at"
            value={basis.forecast_as_of_date ? businessDate(basis.forecast_as_of_date) : "—"}
          />
        </PositionSupport>
      </Card>

      {!summary.has_active_forecast ? (
        <Banner tone="warning" action={<Button onClick={onOpenForecast}>Open Forecast</Button>}>
          <strong>Forecast-dependent figures unavailable.</strong> No cashflow forecast is in force. Actual cash is shown above. Funding requirements, projected cash, collection coverage and investment returns are unavailable until a forecast is activated. Missing forecasts do not mean no funding is needed.
        </Banner>
      ) : null}

      {summary.has_active_forecast && summary.staleness?.is_stale ? (
        <Banner tone="warning" action={<Button onClick={onOpenForecast}>Open Forecast</Button>}>
          The forecast in force was built on sources that have since changed.
          Its figures are what was approved and are still reported exactly as
          approved — see the Forecast section for what moved.
        </Banner>
      ) : null}

      {summary.has_active_forecast ? <>
      <FundingWindows summary={summary} />

      <div className="split split-even">
        <Card
          title="When cash runs short"
          description="The lowest the spendable balance is expected to go across the whole horizon."
        >
          <Position compact>
            <PositionFigure
              label="Lowest projected cash position"
              value={money(peak.minimum_unrestricted_cash, currency)}
              tone={shortOfCash ? "danger" : "neutral"}
            />
            <PositionFigure
              label="Peak funding requirement"
              value={money(peak.peak_funding_deficit, currency)}
              tone={shortOfCash ? "danger" : "success"}
            />
          </Position>
          <PositionSupport>
            <PositionSupportItem
              label="Expected"
              value={peak.peak_deficit_month ? businessDate(peak.peak_deficit_month) : "No month runs short"}
            />
          </PositionSupport>
          <p className="footnote">
            The lowest position is a signed balance: below zero means the project
            cannot meet its commitments that month. The requirement is what has
            to be raised so it never goes below zero.
          </p>
        </Card>

        <Card
          title="Forecast collection coverage"
          description="Whether expected collections cover what the project expects to spend."
        >
          {position.forecast_collection_coverage === null ? (
            <p className="footnote">
              Not meaningful: nothing is forecast to go out over the remaining
              horizon, so there is nothing for collections to cover.
            </p>
          ) : (
            <Position compact>
              <PositionFigure
                label="Coverage"
                value={percent(position.forecast_collection_coverage)}
                tone={isPositive(position.forecast_collection_coverage) ? "neutral" : "warning"}
              />
            </Position>
          )}
          <PositionSupport>
            <PositionSupportItem
              label="Expected usable inflows"
              value={money(position.coverage_numerator, currency)}
            />
            <PositionSupportItem
              label="Expected outflows"
              value={money(position.coverage_denominator, currency)}
            />
          </PositionSupport>
        </Card>
      </div>

      <Returns returns={returns} currency={currency} />
      </> : null}
    </div>
  );
}

/**
 * Thirty, sixty and ninety literal days from the cutoff.
 *
 * The requirement is the figure somebody takes to a bank, and it is shown with
 * the three facts that produced it: the cash the window opened on, what is
 * expected to move, and the deepest point in between. A window that closes in
 * credit can still be short in the middle of it, which is why the trough is
 * beside the closing position rather than instead of it.
 */
function FundingWindows({ summary }: { summary: CashflowSummary }) {
  const currency = summary.basis.currency_code;
  return (
    <Card
      title="Funding position"
      description="What the project must raise to get through the next 30, 60 and 90 days."
    >
      {/* One row per window: three hero cards repeated the same six facts and
          made "nothing needed" the largest thing on the page. */}
      <TableScroll label="Funding by window">
        <thead>
          <tr>
            <th scope="col">Window</th>
            <th scope="col" className="num">Funding required</th>
            <th scope="col" className="num">Opening usable cash</th>
            <th scope="col" className="num">Expected usable inflows</th>
            <th scope="col" className="num">Expected outflows</th>
            <th scope="col" className="num">Lowest projected</th>
            <th scope="col" className="num">Closing projected</th>
          </tr>
        </thead>
        <tbody>
          {summary.funding_windows.map((window) => {
            const needed = isPositive(window.funding_requirement);
            return (
              <tr key={window.days}>
                <th scope="row">
                  Next {window.days} days
                  <span className="cell-secondary">To {businessDate(window.to_date)}</span>
                </th>
                <td className="num">
                  <span className={needed ? "figure-danger" : undefined}>{money(window.funding_requirement, currency)}</span>
                  <span className="cell-secondary">{needed ? "Goes below zero in this window" : "Stays in credit"}</span>
                </td>
                <td className="num">{money(window.opening_unrestricted_cash, currency)}</td>
                <td className="num">{money(window.usable_inflows, currency)}</td>
                <td className="num">{money(window.outflows, currency)}</td>
                <td className="num">{money(window.minimum_projected_unrestricted_cash, currency)}</td>
                <td className="num">{money(window.closing_projected_unrestricted_cash, currency)}</td>
              </tr>
            );
          })}
        </tbody>
      </TableScroll>
      <StatStrip>
        <StatStripNote>
          Literal day windows from {businessDate(summary.basis.as_of_date)}, not calendar months.
          The requirement is driven by the deepest point inside each window, not by where it closes.
        </StatStripNote>
      </StatStrip>
    </Card>
  );
}

/**
 * What the project earns, and on what basis.
 *
 * The basis is part of the number and is on screen rather than in a tooltip: a
 * project NPV and a levered one differ by every financing flow, and a figure
 * labelled only "NPV" invites the reader to assume whichever they expected. An
 * IRR that cannot be computed says why. It never says 0%.
 */
function Returns({
  returns,
  currency,
}: {
  returns: CashflowSummary["returns"];
  currency: string | null;
}) {
  return (
    <Card title="Return" description="What the project earns, and what the investor earns.">
      <div className="split split-even">
        <SubPanel title="Project NPV">
          <Position compact>
            <PositionFigure
              label="Net present value"
              value={money(returns.net_present_value, currency)}
              tone={isPositive(returns.net_present_value) ? "success" : "danger"}
            />
          </Position>
          <KeyValueGrid columns={2}>
            <KeyValue
              label="Net project cashflow"
              value={money(returns.net_project_cashflow, currency)}
              mono
            />
            <KeyValue
              label="Discount rate per period"
              value={percent(returns.discount_rate_per_period)}
              mono
            />
          </KeyValueGrid>
          <p className="footnote">
            <Tooltip term="NPV">Net present value: future cash flows discounted back to today&rsquo;s money.</Tooltip>{" "}
            of operating and development cash, discounted at the forecast&rsquo;s own
            monthly rate. Financing flows are excluded: equity is how the project
            was funded, not what it earned.
          </p>
        </SubPanel>

        <SubPanel title="Equity IRR">
          {returns.equity_irr_per_period === null ? (
            <>
              <Badge tone="neutral">Not available</Badge>
              <p className="footnote">
                {returns.equity_irr_unavailable_reason
                  ? irrReasonLabel(returns.equity_irr_unavailable_reason)
                  : "This return cannot be computed from the equity flows recorded."}
              </p>
            </>
          ) : (
            <Position compact>
              <PositionFigure
                label="Equity IRR per period"
                value={percent(returns.equity_irr_per_period)}
                tone={isPositive(returns.equity_irr_per_period) ? "success" : "danger"}
              />
            </Position>
          )}
          <KeyValueGrid columns={2}>
            <KeyValue label="Equity contributed" value={money(returns.equity_contributed, currency)} mono />
            <KeyValue label="Equity distributed" value={money(returns.equity_distributed, currency)} mono />
            <KeyValue label="Net to investor" value={money(returns.equity_net, currency)} mono />
          </KeyValueGrid>
          <p className="footnote">
            <Tooltip term="IRR">Internal rate of return: the discount rate at which the discounted equity paid in and paid out net to zero.</Tooltip>{" "}
            stated from the investor&rsquo;s side: a contribution is cash they paid
            out and a distribution is cash they received back.
          </p>
        </SubPanel>
      </div>
      <SectionHeader title="Basis" />
      <KeyValueGrid columns={2}>
        <KeyValue label={<><Tooltip term="NPV">Net present value: future cash flows discounted back to today.</Tooltip> basis</>} value={returns.npv_basis.replace(/_/g, " ")} />
        <KeyValue label={<>Equity <Tooltip term="IRR">Internal rate of return: the yearly return at which the cash flows break even.</Tooltip> basis</>} value={returns.equity_irr_basis.replace(/_/g, " ")} />
      </KeyValueGrid>
    </Card>
  );
}
