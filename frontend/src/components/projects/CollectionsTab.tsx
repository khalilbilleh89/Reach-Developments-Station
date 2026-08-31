"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  Badge,
  Button,
  Card,
  EmptyState,
  Field,
  FilterBar,
  Loading,
  Notice,
  TableScroll,
} from "@/components/ui";
import { ApiError, collections } from "@/lib/api";
import type { AgingRow, CollectionProjectSummary, CollectionRegisterRow } from "@/lib/api";
import { useCurrencyCode } from "@/lib/currency";
import { businessDate, isPositive, money, todayISO } from "@/lib/format";

import { CollectionAccount } from "@/components/projects/collections/CollectionAccount";
import { CollectionsSummary } from "@/components/projects/collections/CollectionsSummary";
import {
  AGING_BUCKETS,
  bucketLabel,
  bucketTone,
  installmentLabel,
  installmentTone,
  unitCollectionLabel,
  unitCollectionTone,
} from "@/components/projects/collections/labels";

const VIEWS = [
  { key: "accounts", label: "Accounts" },
  { key: "aging", label: "Aging" },
];

/**
 * The collections workspace: one line per account, and the aging behind it.
 *
 * Built for somebody who opens it every morning, so density beats decoration:
 * money right-aligned in a tabular face, delinquency obvious without reading a
 * number, and the drill from a project total down to the receipt that proves it
 * never more than two clicks.
 *
 * The `as of` control is a real parameter, not a filter over what was loaded.
 * Aging is derived at read time from append-only rows, so asking what the
 * position was at the end of last month is an ordinary question with an exact
 * answer — and month-end reporting and an auditor both ask it.
 *
 * Every filter that could hide money narrows the rows in the browser only
 * *after* the server has already narrowed them by phase and by advisor. The
 * server decides what this caller may see; these controls decide what they want
 * to look at.
 */
export function CollectionsTab({
  projectId,
  roles,
}: {
  projectId: string;
  roles: Set<string>;
}) {
  const [view, setView] = useState("accounts");
  const [asOf, setAsOf] = useState(todayISO());
  const [summary, setSummary] = useState<CollectionProjectSummary | null>(null);
  const [rows, setRows] = useState<CollectionRegisterRow[] | null>(null);
  const [aging, setAging] = useState<AgingRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [bucket, setBucket] = useState("");
  const [overdueOnly, setOverdueOnly] = useState(false);
  const [unappliedOnly, setUnappliedOnly] = useState(false);
  const [disputedOnly, setDisputedOnly] = useState(false);
  const [open, setOpen] = useState<CollectionRegisterRow | null>(null);
  const currencyCodeOf = useCurrencyCode();

  const load = useCallback(async () => {
    try {
      const [totals, register] = await Promise.all([
        collections.summary(projectId, asOf),
        collections.receivables(projectId, asOf),
      ]);
      setSummary(totals);
      setRows(register);
      setError(null);
    } catch (caught) {
      setSummary(null);
      setRows(null);
      setError(
        caught instanceof ApiError ? caught.message : "Could not load the collections position.",
      );
    }
  }, [projectId, asOf]);

  useEffect(() => {
    void (async () => {
      await load();
    })();
  }, [load]);

  const loadAging = useCallback(async () => {
    try {
      setAging(await collections.aging(projectId, { asOf, overdueOnly }));
    } catch {
      setAging([]);
    }
  }, [projectId, asOf, overdueOnly]);

  useEffect(() => {
    void (async () => {
      if (view === "aging") await loadAging();
    })();
  }, [view, loadAging]);

  const visible = useMemo(() => {
    if (rows === null) return [];
    const needle = search.trim().toLowerCase();
    return rows.filter((row) => {
      if (
        needle &&
        ![row.sale_number, row.unit_number, row.client_display_name, row.spa_number ?? ""].some(
          (value) => value.toLowerCase().includes(needle),
        )
      ) {
        return false;
      }
      if (status && row.summary.derived_collection_status !== status) return false;
      if (overdueOnly && !isPositive(row.summary.overdue_total)) return false;
      if (unappliedOnly && !isPositive(row.summary.unapplied_cash)) return false;
      if (disputedOnly && row.summary.open_disputes === 0) return false;
      if (bucket && !row.summary.installments.some((line) => line.bucket === bucket)) return false;
      return true;
    });
  }, [rows, search, status, overdueOnly, unappliedOnly, disputedOnly, bucket]);

  const currencyFor = (row: { currency_id: string }) => currencyCodeOf(row.currency_id);

  return (
    <div className="stack">
      {error ? <Notice tone="error">{error}</Notice> : null}

      <Card
        title="Collections"
        description="What the buyers have actually paid, what is still owed, and how old it is."
      >
        <FilterBar
          actions={
            <>
              {VIEWS.map((option) => (
                <Button
                  key={option.key}
                  variant={view === option.key ? "primary" : undefined}
                  onClick={() => setView(option.key)}
                >
                  {option.label}
                </Button>
              ))}
            </>
          }
        >
          <Field label="As at" hint="Aging is derived for this date, not snapshotted.">
            <input
              type="date"
              value={asOf}
              onChange={(event) => setAsOf(event.target.value || todayISO())}
            />
          </Field>
          <Field label="Search" grow>
            <input
              value={search}
              placeholder="Unit, buyer or contract"
              onChange={(event) => setSearch(event.target.value)}
            />
          </Field>
          <Field label="Status">
            <select value={status} onChange={(event) => setStatus(event.target.value)}>
              <option value="">Any</option>
              {["current", "partially_paid", "overdue", "disputed", "cleared", "cancelled"].map(
                (value) => (
                  <option key={value} value={value}>
                    {unitCollectionLabel(value)}
                  </option>
                ),
              )}
            </select>
          </Field>
          <Field label="Age">
            <select value={bucket} onChange={(event) => setBucket(event.target.value)}>
              <option value="">Any</option>
              {AGING_BUCKETS.map((value) => (
                <option key={value} value={value}>
                  {bucketLabel(value)}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Only show">
            <span className="filter-checks">
              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={overdueOnly}
                  onChange={(event) => setOverdueOnly(event.target.checked)}
                />
                Overdue
              </label>
              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={unappliedOnly}
                  onChange={(event) => setUnappliedOnly(event.target.checked)}
                />
                Unapplied cash
              </label>
              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={disputedOnly}
                  onChange={(event) => setDisputedOnly(event.target.checked)}
                />
                Disputed
              </label>
            </span>
          </Field>
        </FilterBar>

        {summary ? (
          <CollectionsSummary
            summary={summary}
            currencyCode={rows && rows.length > 0 ? currencyFor(rows[0]) : null}
          />
        ) : null}
      </Card>

      {rows === null ? (
        <Loading label="Loading the receivables" />
      ) : view === "accounts" ? (
        visible.length === 0 ? (
          <EmptyState
            title={rows.length === 0 ? "Nothing to collect yet" : "No account matches"}
            hint={
              rows.length === 0
                ? "No sale in this project has a payment schedule to collect against."
                : "No account matches these filters. Widen them to see the rest."
            }
          />
        ) : (
          <Card title={`${visible.length} account${visible.length === 1 ? "" : "s"}`}>
            <TableScroll label="Receivables" fixedFirst>
              <thead>
                <tr>
                  <th scope="col">Unit</th>
                  <th scope="col">Buyer</th>
                  <th scope="col">Contract</th>
                  <th scope="col" className="num">
                    Scheduled
                  </th>
                  <th scope="col" className="num">
                    Collected
                  </th>
                  <th scope="col" className="num">
                    Unapplied
                  </th>
                  <th scope="col" className="num">
                    Outstanding
                  </th>
                  <th scope="col" className="num">
                    Overdue
                  </th>
                  <th scope="col" className="num">
                    Oldest
                  </th>
                  <th scope="col">State</th>
                  <th scope="col">Next</th>
                  <th scope="col">
                    <span className="visually-hidden">Open</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {visible.map((row) => {
                  const code = currencyFor(row);
                  return (
                    <tr key={row.sale_id}>
                      <th scope="row">{row.unit_number}</th>
                      <td>{row.client_display_name}</td>
                      <td className="mono">{row.sale_number}</td>
                      <td className="num mono">
                        {money(row.summary.scheduled_total, code)}
                      </td>
                      <td className="num mono">
                        {money(row.summary.allocated_total, code)}
                      </td>
                      <td className="num mono">
                        {isPositive(row.summary.unapplied_cash) ? (
                          <Badge tone="warning">
                            {money(row.summary.unapplied_cash, code)}
                          </Badge>
                        ) : (
                          money(row.summary.unapplied_cash, code)
                        )}
                      </td>
                      <td className="num mono">
                        {money(row.summary.outstanding_total, code)}
                      </td>
                      <td className="num mono">{money(row.summary.overdue_total, code)}</td>
                      <td className="num mono">
                        {row.summary.oldest_overdue_days > 0
                          ? `${row.summary.oldest_overdue_days} d`
                          : "—"}
                      </td>
                      <td>
                        <Badge tone={unitCollectionTone(row.summary.derived_collection_status)}>
                          {unitCollectionLabel(row.summary.derived_collection_status)}
                        </Badge>
                        {row.summary.open_disputes > 0 ? (
                          <p className="hint">
                            {row.summary.open_disputes} disputed, still owed
                          </p>
                        ) : null}
                      </td>
                      <td>{businessDate(row.summary.next_action_date)}</td>
                      <td>
                        <Button onClick={() => setOpen(row)}>Open</Button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </TableScroll>
          </Card>
        )
      ) : aging === null ? (
        <Loading label="Loading the aging" />
      ) : aging.length === 0 ? (
        <EmptyState
          title="Nothing aged"
          hint={`No overdue receivables as at ${businessDate(asOf)}.`}
        />
      ) : (
        <Card title={`Aging as at ${businessDate(asOf)}`}>
          <TableScroll label="Aging" fixedFirst>
            <thead>
              <tr>
                <th scope="col">Unit</th>
                <th scope="col">Buyer</th>
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
                <th scope="col">Age</th>
                <th scope="col">State</th>
              </tr>
            </thead>
            <tbody>
              {aging.map((row) => {
                const code = currencyCodeOf(row.currency_id);
                const line = row.installment;
                return (
                  <tr key={`${row.sale_id}-${line.installment_id}`}>
                    <th scope="row">{row.unit_number}</th>
                    <td>{row.client_display_name}</td>
                    <td>
                      {line.sequence}. {line.label}
                    </td>
                    <td>{businessDate(line.due_date)}</td>
                    <td className="num mono">{money(line.scheduled, code)}</td>
                    <td className="num mono">{money(line.paid, code)}</td>
                    <td className="num mono">{money(line.outstanding, code)}</td>
                    <td className="num mono">
                      {line.overdue_days > 0 ? line.overdue_days : "—"}
                    </td>
                    <td>
                      <Badge tone={bucketTone(line.bucket)}>{bucketLabel(line.bucket)}</Badge>
                    </td>
                    <td>
                      <Badge tone={installmentTone(line.status)}>
                        {installmentLabel(line.status)}
                      </Badge>
                      {line.has_active_waiver ? (
                        <p className="hint">Collection paused, balance still due</p>
                      ) : null}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </TableScroll>
        </Card>
      )}

      {open ? (
        <CollectionAccount
          projectId={projectId}
          saleId={open.sale_id}
          saleNumber={open.sale_number}
          unitNumber={open.unit_number}
          clientName={open.client_display_name}
          currencyCode={currencyFor(open)}
          roles={roles}
          onClose={() => setOpen(null)}
          onChanged={() => {
            void load();
            if (view === "aging") void loadAging();
          }}
        />
      ) : null}
    </div>
  );
}
