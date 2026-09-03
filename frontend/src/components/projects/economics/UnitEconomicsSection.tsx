"use client";

import type { UnitEconomicsDetail } from "@/lib/api";
import type { Answer } from "@/lib/answer";
import {
  Badge,
  EmptyState,
  KeyValue,
  KeyValueGrid,
  Loading,
  Metric,
  MetricGroup,
  Notice,
  SectionHeader,
  TableScroll,
  Waterfall,
  WaterfallRow,
} from "@/components/ui";
import { useCurrencyCode } from "@/lib/currency";
import { businessDate, money, percent } from "@/lib/format";

import {
  PROFIT_EXPLANATIONS,
  basisLabel,
  costBasisLabel,
  costTypeLabel,
  profitTone,
  profitabilityLabel,
  profitabilityTone,
} from "./labels";

/**
 * What one unit costs and what it earns, inside Unit 360.
 *
 * Two things on this panel are load-bearing and easy to lose.
 *
 * **The cost basis is named.** A sold unit is analysed on the allocation
 * version that governed when its contract was signed, not on today's. Two units
 * side by side can therefore carry different land cost, and the version stamp is
 * how a reader finds out why rather than concluding the system is wrong.
 *
 * **An absent margin says why.** Where profit cannot be calculated the panel
 * prints the reason and no number. A zero in that position is a number people
 * act on, and it would be the wrong one.
 *
 * The waterfall is the server's, step by step and in its order, because the
 * order *is* the calculation. Access is enforced by the API, not here: the unit
 * file asks only on behalf of a role the server answers, and a refusal it still
 * returns is said in words. This component never receives figures and hides
 * them.
 */
export function UnitEconomicsSection({ answer }: { answer: Answer<UnitEconomicsDetail> }) {
  const currencyCodeOf = useCurrencyCode();

  if (answer.status === "off") {
    return (
      <EmptyState
        title="Not available to your role"
        hint="Unit cost and margin are restricted to Finance, the CFO, project management, executives and audit."
      />
    );
  }
  if (answer.status === "denied") {
    return (
      <EmptyState
        title="Not available to your role"
        hint="Unit cost and margin are restricted to Finance, the CFO, project management, executives and audit."
      />
    );
  }
  if (answer.status === "failed") {
    return <Notice tone="error">{answer.message}</Notice>;
  }
  if (answer.status === "loading") {
    return <Loading label="Loading the unit's economics" shape="page" />;
  }

  const detail = answer.data;
  const row = detail.economics;
  // The API says which currency the cost is denominated in, so the panel does
  // not have to assume it matches the price beside it — and on a
  // currency-mismatch unit it deliberately does not.
  const costCode = currencyCodeOf(row.cost_currency_id);
  // And revenue is denominated separately, because on a currency-mismatch unit
  // it genuinely is. Printing it under the cost currency would state a
  // conversion nobody approved.
  const revenueCode = currencyCodeOf(row.revenue_currency_id);
  const ready = row.profitability_status === "ready";
  const lastStep = detail.waterfall[detail.waterfall.length - 1];

  return (
    <>
      <section>
        <SectionHeader
          title="Position"
          actions={
            <>
              <Badge tone={row.basis === "sold" ? "info" : "neutral"}>{basisLabel(row.basis)} basis</Badge>
              <Badge tone={profitabilityTone(row.profitability_status)}>
                {profitabilityLabel(row.profitability_status)}
              </Badge>
              {row.below_margin_threshold ? (
                <Badge tone="warning">Below {percent(row.threshold_fraction)} minimum</Badge>
              ) : null}
            </>
          }
        />

        {ready ? null : <Notice tone="warning">{PROFIT_EXPLANATIONS[row.profitability_status]}</Notice>}

        <MetricGroup>
          <Metric
            label="Revenue"
            value={money(row.revenue, revenueCode)}
            note={row.revenue_source === "sale_contract" ? "Frozen contract terms" : "Current approved price"}
          />
          <Metric label="Total cost" value={money(row.total_cost, costCode)} />
          <Metric
            label="Profit after finance"
            value={money(row.profit_after_finance, costCode)}
            tone={profitTone(row.profit_after_finance) === "danger" ? "danger" : "neutral"}
            note={profitTone(row.profit_after_finance) === "danger" ? "A loss" : undefined}
          />
          <Metric
            label="Margin"
            value={percent(row.margin_fraction)}
            tone={row.below_margin_threshold ? "warning" : "neutral"}
          />
          <Metric label="Return on cost" value={percent(row.return_on_cost_fraction)} size="sm" />
        </MetricGroup>

        <p className="footnote">
          {row.allocation_version_number === null
            ? "No cost allocation version governs this unit."
            : `Cost basis v${row.allocation_version_number}, effective ` +
              `${businessDate(row.allocation_effective_from)}.`}{" "}
          {row.basis === "sold"
            ? "A sold unit keeps the basis that governed when its contract was signed, so it does not move when a newer one is activated."
            : "An unsold unit is analysed on the current basis and the current approved price, so both move when either is revised."}
        </p>
      </section>

      {detail.waterfall.length > 0 ? (
        <section>
          <SectionHeader
            title="From revenue to profit"
            description="Each step is the server's, in the order it was applied."
          />
          <Waterfall>
            {detail.waterfall.map((step) => (
              <WaterfallRow
                key={step.key}
                label={step.label}
                amount={money(step.amount, step.key === "revenue" ? revenueCode : costCode)}
                kind={step === lastStep ? "total" : step.is_subtotal ? "subtotal" : "line"}
              />
            ))}
          </Waterfall>
        </section>
      ) : null}

      <section>
        <SectionHeader title="Cost composition" />
        <KeyValueGrid columns={3}>
          <KeyValue label="Land" mono value={money(row.land_cost, costCode)} />
          <KeyValue label="Hard" mono value={money(row.hard_cost, costCode)} />
          <KeyValue label="Soft" mono value={money(row.soft_cost, costCode)} />
          <KeyValue label="Direct" mono value={money(row.direct_cost, costCode)} />
          <KeyValue label="Variable selling" mono value={money(row.variable_selling_cost, costCode)} />
          <KeyValue label="Seller cost" mono value={money(row.seller_cost, costCode)} />
          <KeyValue label="Allocated finance" mono value={money(row.allocated_finance_cost, costCode)} />
          <KeyValue label="Deal finance" mono value={money(row.deal_finance_cost, costCode)} />
          <KeyValue label="Finance counted" mono value={money(row.finance_cost, costCode)} />
        </KeyValueGrid>
      </section>

      <section>
        <SectionHeader title="Unit-specific costs" />
        {detail.unit_costs.length === 0 ? (
          <EmptyState
            compact
            title="No unit-specific costs recorded"
            hint="Upgrades, furniture, commissions and other costs belonging to this unit alone would appear here."
          />
        ) : (
          <TableScroll label="Unit costs" compact>
            <thead>
              <tr>
                <th scope="col">Cost</th>
                <th scope="col">Basis</th>
                <th scope="col">Date</th>
                <th scope="col" className="num">
                  Amount
                </th>
                <th scope="col">State</th>
              </tr>
            </thead>
            <tbody>
              {detail.unit_costs.map((cost) => (
                <tr key={cost.id}>
                  <th scope="row">{costTypeLabel(cost.cost_type)}</th>
                  <td>{costBasisLabel(cost.basis)}</td>
                  <td>{businessDate(cost.effective_date)}</td>
                  <td className="num">{money(cost.amount, costCode)}</td>
                  <td>
                    <Badge tone={cost.status === "reversed" ? "danger" : "neutral"}>
                      {cost.status === "reversed" ? "Reversed" : "Counted"}
                    </Badge>
                    {cost.reversal_reason ? <p className="hint">{cost.reversal_reason}</p> : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </TableScroll>
        )}
      </section>
    </>
  );
}
