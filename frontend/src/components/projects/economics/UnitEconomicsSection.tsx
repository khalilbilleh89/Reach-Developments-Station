"use client";

import { useCallback, useEffect, useState } from "react";

import {
  Badge,
  EmptyState,
  KeyValue,
  KeyValueGrid,
  Loading,
  Notice,
  SectionHeader,
  Stat,
  StatRow,
  TableScroll,
} from "@/components/ui";
import { ApiError, unitEconomics } from "@/lib/api";
import type { UnitEconomicsDetail } from "@/lib/api";
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
 * Access is enforced by the API, not here. A role that may not see cost gets a
 * 403 and this panel says so — it never receives the figures and hides them.
 */
export function UnitEconomicsSection({
  projectId,
  unitId,
}: {
  projectId: string;
  unitId: string;
}) {
  const currencyCodeOf = useCurrencyCode();
  const [detail, setDetail] = useState<UnitEconomicsDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [denied, setDenied] = useState(false);

  const load = useCallback(async () => {
    try {
      setDetail(await unitEconomics.unit(projectId, unitId));
      setError(null);
      setDenied(false);
    } catch (caught) {
      setDetail(null);
      // Only a 403 is a role problem. Saying "your role" for a 500 or a dropped
      // connection sends somebody to ask for a permission they already have.
      setDenied(caught instanceof ApiError && caught.isForbidden);
      setError(
        caught instanceof ApiError && caught.isForbidden
          ? null
          : caught instanceof ApiError
            ? caught.message
            : "Could not load this unit's economics.",
      );
    }
  }, [projectId, unitId]);

  useEffect(() => {
    void (async () => {
      await load();
    })();
  }, [load]);

  if (denied) {
    return (
      <section>
        <SectionHeader title="Economics" />
        <EmptyState
          title="Not available to your role"
          hint="Unit cost and margin are restricted to Finance, the CFO, project management, executives and audit."
        />
      </section>
    );
  }
  if (error) {
    return (
      <section>
        <SectionHeader title="Economics" />
        <Notice tone="error">{error}</Notice>
      </section>
    );
  }
  if (detail === null) {
    return (
      <section>
        <SectionHeader title="Economics" />
        <Loading label="Loading the unit's economics" />
      </section>
    );
  }

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

  return (
    <section>
      <SectionHeader
        title="Economics"
        actions={
          <>
            <Badge tone={row.basis === "sold" ? "info" : "neutral"}>
              {basisLabel(row.basis)} basis
            </Badge>
            <Badge tone={profitabilityTone(row.profitability_status)}>
              {profitabilityLabel(row.profitability_status)}
            </Badge>
            {row.below_margin_threshold ? (
              <Badge tone="warning">
                Below {percent(row.threshold_fraction)} minimum
              </Badge>
            ) : null}
          </>
        }
      />

      {ready ? null : (
        <Notice tone="warning">{PROFIT_EXPLANATIONS[row.profitability_status]}</Notice>
      )}

      <StatRow>
        <Stat
          label="Revenue"
          value={money(row.revenue, revenueCode)}
          note={
            row.revenue_source === "sale_contract"
              ? "Frozen contract terms"
              : "Current approved price"
          }
          small
        />
        <Stat label="Total cost" value={money(row.total_cost, costCode)} small />
        <Stat
          label="Profit after finance"
          value={money(row.profit_after_finance, costCode)}
          note={profitTone(row.profit_after_finance) === "danger" ? "A loss" : undefined}
          small
        />
        <Stat label="Margin" value={percent(row.margin_fraction)} small />
        <Stat label="Return on cost" value={percent(row.return_on_cost_fraction)} small />
      </StatRow>

      <KeyValueGrid columns={3}>
        <KeyValue label="Land" mono value={money(row.land_cost, costCode)} />
        <KeyValue label="Hard" mono value={money(row.hard_cost, costCode)} />
        <KeyValue label="Soft" mono value={money(row.soft_cost, costCode)} />
        <KeyValue label="Direct" mono value={money(row.direct_cost, costCode)} />
        <KeyValue
          label="Variable selling"
          mono
          value={money(row.variable_selling_cost, costCode)}
        />
        <KeyValue label="Seller cost" mono value={money(row.seller_cost, costCode)} />
        <KeyValue
          label="Finance"
          mono
          value={money(row.finance_cost ?? row.allocated_finance_cost, costCode)}
        />
        <KeyValue label="Gross profit" mono value={money(row.gross_profit, costCode)} />
        <KeyValue
          label="Contribution"
          mono
          value={money(row.contribution_profit, costCode)}
        />
      </KeyValueGrid>

      <p className="footnote">
        {row.allocation_version_number === null
          ? "No cost allocation version governs this unit."
          : `Cost basis v${row.allocation_version_number}, effective ` +
            `${businessDate(row.allocation_effective_from)}.`}{" "}
        {row.basis === "sold"
          ? "A sold unit keeps the basis that governed when its contract was signed, so it does not move when a newer one is activated."
          : "An unsold unit is analysed on the current basis and the current approved price, so both move when either is revised."}
      </p>

      {detail.unit_costs.length === 0 ? (
        <EmptyState
          title="No unit-specific costs recorded"
          hint="Upgrades, furniture, commissions and other costs belonging to this unit alone would appear here."
        />
      ) : (
        <TableScroll label="Unit costs">
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
                <td className="num mono">{money(cost.amount, costCode)}</td>
                <td>
                  <Badge tone={cost.status === "reversed" ? "danger" : "neutral"}>
                    {cost.status === "reversed" ? "Reversed" : "Counted"}
                  </Badge>
                  {cost.reversal_reason ? (
                    <p className="hint">{cost.reversal_reason}</p>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </TableScroll>
      )}
    </section>
  );
}
