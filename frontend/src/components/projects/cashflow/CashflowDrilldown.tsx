"use client";

import { useCallback, useEffect, useState } from "react";

import {
  Badge,
  Drawer,
  EmptyState,
  DataToolbar,
  Loading,
  Notice,
  TableScroll,
  ToolbarFilter,
} from "@/components/ui";
import { cashflow, cashflowCsvHref } from "@/lib/api";
import type { CashflowDrilldown as Drilldown } from "@/lib/api";
import type { Answer } from "@/lib/answer";
import { toAnswer } from "@/lib/answer";
import { businessDate, money } from "@/lib/format";

import {
  ROW_BASIS_OPTIONS,
  SOURCE_TYPE_OPTIONS,
  categoryLabel,
  rowBasisLabel,
  sourceTypeLabel,
  sourceTypeOwner,
} from "./labels";

export interface DrilldownQuery {
  periodMonth?: string;
  category?: string;
  sourceType?: string;
  flowDirection?: string;
  basis?: string;
}

/**
 * The transactions behind a figure, and which system owns each of them.
 *
 * Management reporting without lineage is an assertion. Every row here is a
 * reference to a record another module governs — a collections receipt, a
 * construction payment, a payment-plan instalment — and the owning module is
 * named beside it, because a reader who has to correct a number needs to know
 * where to go. Flattening them all to "cashflow transaction" would hide exactly
 * that, and this platform deliberately keeps no shadow reporting ledger.
 */
export function CashflowDrilldown({
  projectId,
  asOf,
  query,
  onClose,
}: {
  projectId: string;
  asOf: string | null;
  query: DrilldownQuery;
  onClose: () => void;
}) {
  // Seeded from the figure that was opened, then owned by this drawer. The
  // parent remounts it (see its `key`) when a different figure is opened, which
  // is what re-seeds these rather than an effect copying a prop into state.
  const [filters, setFilters] = useState<DrilldownQuery>(query);
  const [answer, setAnswer] = useState<Answer<Drilldown>>({ status: "loading" });

  const load = useCallback(async () => {
    setAnswer({ status: "loading" });
    try {
      const data = await cashflow.drilldown(projectId, {
        asOf: asOf ?? undefined,
        periodMonth: filters.periodMonth,
        category: filters.category,
        basis: filters.basis,
        sourceType: filters.sourceType,
        flowDirection: filters.flowDirection,
      });
      setAnswer({ status: "ready", data });
    } catch (caught) {
      setAnswer(toAnswer(caught));
    }
  }, [projectId, asOf, filters]);

  useEffect(() => {
    void (async () => {
      await load();
    })();
  }, [load]);

  const currency =
    answer.status === "ready" ? answer.data.basis.currency_code : null;

  return (
    <Drawer
      eyebrow="Cashflow"
      title={
        filters.periodMonth
          ? `Transactions in ${businessDate(filters.periodMonth)}`
          : "Transactions behind the figures"
      }
      subtitle="Every row is a record another module owns. Nothing here is a copy."
      facts={
        answer.status === "ready"
          ? [
              { label: "Rows", value: String(answer.data.rows.length) },
              { label: "Total", value: money(answer.data.total, currency) },
              { label: "As at", value: businessDate(answer.data.basis.as_of_date) },
            ]
          : undefined
      }
      actions={
        <a
          className="button"
          href={cashflowCsvHref(projectId, "drilldown", {
            asOf: asOf ?? undefined,
            periodMonth: filters.periodMonth,
            category: filters.category,
            basis: filters.basis,
            sourceType: filters.sourceType,
            flowDirection: filters.flowDirection,
          })}
        >
          Export CSV
        </a>
      }
      onClose={onClose}
    >
      <DataToolbar>
        <ToolbarFilter label="Source" active={Boolean(filters.sourceType)}>
          <select
            className="input"
            value={filters.sourceType ?? ""}
            onChange={(event) =>
              setFilters((current) => ({
                ...current,
                sourceType: event.target.value || undefined,
              }))
            }
          >
            <option value="">Every source</option>
            {SOURCE_TYPE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </ToolbarFilter>
        <ToolbarFilter label="Basis" active={Boolean(filters.basis)}>
          <select
            className="input"
            value={filters.basis ?? ""}
            onChange={(event) =>
              setFilters((current) => ({ ...current, basis: event.target.value || undefined }))
            }
          >
            <option value="">Actual and expected</option>
            {ROW_BASIS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </ToolbarFilter>
        <ToolbarFilter label="Direction" active={Boolean(filters.flowDirection)}>
          <select
            className="input"
            value={filters.flowDirection ?? ""}
            onChange={(event) =>
              setFilters((current) => ({
                ...current,
                flowDirection: event.target.value || undefined,
              }))
            }
          >
            <option value="">In and out</option>
            <option value="inflow">Cash in</option>
            <option value="outflow">Cash out</option>
          </select>
        </ToolbarFilter>
      </DataToolbar>

      {answer.status === "loading" ? (
        <Loading label="Loading the transactions" shape="rows" />
      ) : null}
      {answer.status === "denied" ? (
        <Notice tone="info">These transactions are not available to your role.</Notice>
      ) : null}
      {answer.status === "failed" ? <Notice tone="error">{answer.message}</Notice> : null}

      {answer.status === "ready" ? (
        answer.data.rows.length === 0 ? (
          <EmptyState
            title="Nothing matches"
            hint="No transaction in this period matches the filters above."
          />
        ) : (
          <TableScroll label="Transactions behind this figure" compact>
            <thead>
              <tr>
                <th scope="col">Date</th>
                <th scope="col">Record</th>
                <th scope="col">Owned by</th>
                <th scope="col">Reference</th>
                <th scope="col">Category</th>
                <th scope="col">Basis</th>
                <th scope="col">Direction</th>
                <th scope="col">Status</th>
                <th scope="col" className="num">Amount</th>
              </tr>
            </thead>
            <tbody>
              {answer.data.rows.map((row) => (
                <tr key={`${row.source_type}-${row.source_id}-${row.basis}-${row.business_date}`}>
                  <td>{businessDate(row.business_date)}</td>
                  <td>{sourceTypeLabel(row.source_type)}</td>
                  <td>{sourceTypeOwner(row.source_type)}</td>
                  <td className="cell-prose">{row.display_reference}</td>
                  <td>{categoryLabel(row.category)}</td>
                  <td>
                    <Badge tone="neutral">{rowBasisLabel(row.basis)}</Badge>
                  </td>
                  <td>{row.flow_direction === "inflow" ? "Cash in" : "Cash out"}</td>
                  <td>{row.status}</td>
                  <td className="num">{money(row.amount, currency)}</td>
                </tr>
              ))}
            </tbody>
          </TableScroll>
        )
      ) : null}
    </Drawer>
  );
}
