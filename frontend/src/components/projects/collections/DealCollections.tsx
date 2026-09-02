"use client";

import { useEffect, useState } from "react";

import { Badge, Metric, MetricGroup, Notice, TableScroll } from "@/components/ui";
import { ApiError, collections } from "@/lib/api";
import type { CollectionSaleSummary, Receipt } from "@/lib/api";
import { useCurrencyCode } from "@/lib/currency";
import { businessDate, isPositive, money } from "@/lib/format";

import {
  clearanceLabel,
  clearanceTone,
  installmentLabel,
  installmentTone,
  receiptLabel,
  receiptTone,
  unitCollectionLabel,
  unitCollectionTone,
} from "./labels";

/**
 * The collections position on the deal file: a summary, not a second workspace.
 *
 * The deal file already answers what was agreed. This answers what arrived,
 * with the four figures that must never be conflated — scheduled, confirmed,
 * applied, outstanding — plus the unapplied balance sitting between the second
 * and third. Everything below it is drill-down: the instalments and the last
 * few receipts, enough to answer "which receipt proves that?" without leaving
 * the record.
 *
 * If the contract was cancelled, what is owed back and what has actually left
 * appear side by side. PR-MVP-05 was careful never to call the amount due
 * "refunded", and merging the two here would undo that.
 *
 * Mounted only for a role the server answers: the deal file checks the
 * reader's roles before this section exists, so a Sales Advisor's deal file
 * never requests the account at all.
 */
export function DealCollections({ projectId, saleId }: { projectId: string; saleId: string }) {
  const [summary, setSummary] = useState<CollectionSaleSummary | null>(null);
  const [receipts, setReceipts] = useState<Receipt[]>([]);
  const [problem, setProblem] = useState<string | null>(null);
  const currencyCodeOf = useCurrencyCode();

  useEffect(() => {
    let live = true;
    void (async () => {
      try {
        const [position, rows] = await Promise.all([
          collections.account(projectId, saleId),
          collections.receipts(projectId, saleId).catch(() => [] as Receipt[]),
        ]);
        if (!live) return;
        setSummary(position);
        setReceipts(rows);
        setProblem(null);
      } catch (caught) {
        // A 403 is a fact about this reader; anything else is a fault, and
        // telling somebody their role is wrong when the server returned a 500
        // sends them to an administrator instead of to the logs.
        if (live) {
          setSummary(null);
          setProblem(
            caught instanceof ApiError && caught.isForbidden
              ? "Collections is not available to your role."
              : caught instanceof ApiError
                ? caught.message
                : "Could not load the collections position.",
          );
        }
      }
    })();
    return () => {
      live = false;
    };
  }, [projectId, saleId]);

  if (problem !== null) {
    return <p className="subtle">{problem}</p>;
  }
  if (summary === null) {
    return <p className="subtle">Loading the collections position.</p>;
  }
  if (summary.active_payment_plan_version_id === null) {
    return (
      <p className="subtle">
        There is no active payment schedule on this contract, so there is nothing to collect
        against yet.
      </p>
    );
  }

  const code = currencyCodeOf(summary.currency_id);

  return (
    <div className="stack">
      <MetricGroup>
        <Metric
          label="Position"
          value={
            <Badge tone={unitCollectionTone(summary.derived_collection_status)}>
              {unitCollectionLabel(summary.derived_collection_status)}
            </Badge>
          }
          size="sm"
        />
        <Metric label="Scheduled" value={money(summary.scheduled_total, code)} size="sm" />
        <Metric
          label="Confirmed receipts"
          value={money(summary.confirmed_receipts_total, code)}
          note="Cash Finance accepted"
          size="sm"
        />
        <Metric
          label="Applied"
          value={money(summary.allocated_total, code)}
          note={`${money(summary.unapplied_cash, code)} unapplied`}
          size="sm"
        />
        <Metric
          label="Outstanding"
          value={money(summary.outstanding_total, code)}
          note={`${money(summary.overdue_total, code)} overdue`}
          tone={isPositive(summary.overdue_total) ? "danger" : "neutral"}
          size="sm"
        />
      </MetricGroup>

      {isPositive(summary.unapplied_cash) ? (
        <Notice tone="warning">
          {money(summary.unapplied_cash, code)} of confirmed cash has not been applied to any
          instalment, so it is not reducing the balance.
        </Notice>
      ) : null}

      {summary.open_disputes > 0 || summary.active_waivers > 0 ? (
        <p className="footnote">
          {summary.open_disputes > 0
            ? `${summary.open_disputes} instalment${summary.open_disputes === 1 ? "" : "s"} disputed — balance unchanged. `
            : ""}
          {summary.active_waivers > 0
            ? `${summary.active_waivers} collection hold in force — balance still due.`
            : ""}
        </p>
      ) : null}

      <TableScroll label="Instalments and cash received" compact>
        <thead>
          <tr>
            <th scope="col">Instalment</th>
            <th scope="col">Due</th>
            <th scope="col" className="num">
              Scheduled
            </th>
            <th scope="col" className="num">
              Collected
            </th>
            <th scope="col" className="num">
              Outstanding
            </th>
            <th scope="col" className="num">
              Days
            </th>
            <th scope="col">State</th>
          </tr>
        </thead>
        <tbody>
          {summary.installments.map((row) => (
            <tr key={row.installment_id}>
              <th scope="row">
                {row.sequence}. {row.label}
              </th>
              <td className="figure">{businessDate(row.due_date)}</td>
              <td className="num">{money(row.scheduled, code)}</td>
              <td className="num">{money(row.paid, code)}</td>
              <td className="num">{money(row.outstanding, code)}</td>
              <td className="num">{row.overdue_days > 0 ? row.overdue_days : "—"}</td>
              <td>
                <Badge tone={installmentTone(row.status)}>{installmentLabel(row.status)}</Badge>
              </td>
            </tr>
          ))}
        </tbody>
      </TableScroll>

      {receipts.length > 0 ? (
        <TableScroll label="Receipts" compact>
          <thead>
            <tr>
              <th scope="col">Receipt</th>
              <th scope="col">Date</th>
              <th scope="col" className="num">
                Amount
              </th>
              <th scope="col" className="num">
                Unapplied
              </th>
              <th scope="col">State</th>
            </tr>
          </thead>
          <tbody>
            {receipts.slice(0, 8).map((receipt) => (
              <tr key={receipt.id}>
                <th scope="row" className="mono">
                  {receipt.receipt_number}
                </th>
                <td className="figure">{businessDate(receipt.receipt_date)}</td>
                <td className="num">{money(receipt.amount, code)}</td>
                <td className="num">{money(receipt.unapplied_amount, code)}</td>
                <td>
                  <Badge tone={receiptTone(receipt.status)}>{receiptLabel(receipt.status)}</Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </TableScroll>
      ) : null}

      {isPositive(summary.refund_due_total) || isPositive(summary.refund_confirmed_total) ? (
        <MetricGroup compact>
          <Metric
            label="Refund due"
            value={money(summary.refund_due_total, code)}
            note="Approved on the cancellation"
            size="sm"
          />
          <Metric
            label="Actually refunded"
            value={money(summary.refund_confirmed_total, code)}
            note="Confirmed as having left"
            size="sm"
          />
          <Metric label="Still to pay" value={money(summary.refund_outstanding, code)} size="sm" />
        </MetricGroup>
      ) : null}

      <p className="footnote">
        Collection clearance:{" "}
        <Badge tone={clearanceTone(summary.collection_clearance_status)}>
          {clearanceLabel(summary.collection_clearance_status)}
        </Badge>
        {summary.clearance_blockers.length > 0
          ? ` — ${summary.clearance_blockers.join("; ")}.`
          : " — the ledger is clear."}
      </p>
    </div>
  );
}
