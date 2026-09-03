"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  Badge,
  Card,
  DataToolbar,
  IdentityCell,
  EmptyState,
  Loading,
  Notice,
  PageHeader,
  StatusDot,
  TableScroll,
  ToolbarFilter,
} from "@/components/ui";
import { ApiError, collections } from "@/lib/api";
import type { AgingRow, CollectionProjectSummary, CollectionRegisterRow } from "@/lib/api";
import { useCurrencyCode } from "@/lib/currency";
import { businessDate, isPositive, money, todayISO } from "@/lib/format";
import { sectionDescription } from "@/components/shell/navigation";

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
 * The collections workspace: the position, one line per account, and the
 * aging behind it.
 *
 * Built for somebody who opens it every morning, so density beats decoration:
 * the money that matters — outstanding, due, overdue, unapplied — at the top,
 * the age of it in a strip beneath, and the drill from a project total down to
 * the receipt that proves it never more than two clicks.
 *
 * The `as at` control is a real parameter, not a filter over what was loaded.
 * Aging is derived at read time from append-only rows, so asking what the
 * position was at the end of last month is an ordinary question with an exact
 * answer — and month-end reporting and an auditor both ask it.
 *
 * Every filter that could hide money narrows the rows in the browser only
 * *after* the server has already narrowed them by phase and by advisor. The
 * server decides what this caller may see; these controls decide what they want
 * to look at.
 */
export function CollectionsTab({ projectId, roles }: { projectId: string; roles: Set<string> }) {
  const [view, setView] = useState("accounts");
  const [asOf, setAsOf] = useState(todayISO());
  const [summary, setSummary] = useState<CollectionProjectSummary | null>(null);
  const [rows, setRows] = useState<CollectionRegisterRow[] | null>(null);
  const [aging, setAging] = useState<AgingRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [bucket, setBucket] = useState("");
  const [only, setOnly] = useState("");
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
      setError(caught instanceof ApiError ? caught.message : "Could not load the collections position.");
    }
  }, [projectId, asOf]);

  useEffect(() => {
    void (async () => {
      await load();
    })();
  }, [load]);

  const loadAging = useCallback(async () => {
    try {
      setAging(await collections.aging(projectId, { asOf, overdueOnly: only === "overdue" }));
      setError(null);
    } catch (caught) {
      // An empty aging list and a failed request look identical on screen, and
      // "Nothing aged" is the more reassuring of the two. Say which it was.
      setAging(null);
      setError(caught instanceof ApiError ? caught.message : "Could not load the aging report.");
    }
  }, [projectId, asOf, only]);

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
        ![row.sale_number, row.unit_number, row.client_display_name, row.spa_number ?? ""].some((value) =>
          value.toLowerCase().includes(needle),
        )
      ) {
        return false;
      }
      if (status && row.summary.derived_collection_status !== status) return false;
      if (only === "overdue" && !isPositive(row.summary.overdue_total)) return false;
      if (only === "unapplied" && !isPositive(row.summary.unapplied_cash)) return false;
      if (only === "disputed" && row.summary.open_disputes === 0) return false;
      if (bucket && !row.summary.installments.some((line) => line.bucket === bucket)) return false;
      return true;
    });
  }, [rows, search, status, only, bucket]);

  const currencyFor = (row: { currency_id: string }) => currencyCodeOf(row.currency_id);
  const filtered = search !== "" || status !== "" || bucket !== "" || only !== "";

  return (
    <>
      <PageHeader title="Collections" subtitle={sectionDescription("collections")} compact />

      <div className="stack">
        {error ? <Notice tone="error">{error}</Notice> : null}

        <Card>
          {summary === null ? (
            <Loading label="Loading the position…" shape="metrics" />
          ) : (
            <CollectionsSummary summary={summary} currencyCodeOf={currencyCodeOf} />
          )}
        </Card>

        <DataToolbar
          framed
          search={{ value: search, onChange: setSearch, placeholder: "Unit, buyer or contract", label: "Search accounts" }}
          count={
            rows && view === "accounts"
              ? { shown: visible.length, total: rows.length, noun: "account" }
              : aging && view === "aging"
                ? { shown: aging.length, noun: "instalment" }
                : undefined
          }
          onReset={
            filtered
              ? () => {
                  setSearch("");
                  setStatus("");
                  setBucket("");
                  setOnly("");
                }
              : undefined
          }
          actions={
            <div className="segmented" role="group" aria-label="View">
              {VIEWS.map((option) => (
                <button
                  key={option.key}
                  type="button"
                  className="segment"
                  aria-pressed={view === option.key}
                  onClick={() => setView(option.key)}
                >
                  {option.label}
                </button>
              ))}
            </div>
          }
        >
          <ToolbarFilter label="As at">
            <input
              className="input"
              type="date"
              value={asOf}
              title="Aging is derived for this date, not snapshotted."
              onChange={(event) => setAsOf(event.target.value || todayISO())}
            />
          </ToolbarFilter>
          <ToolbarFilter label="Status" active={status !== ""}>
            <select className="input" value={status} onChange={(event) => setStatus(event.target.value)}>
              <option value="">Any status</option>
              {["current", "partially_paid", "overdue", "disputed", "cleared", "cancelled"].map((value) => (
                <option key={value} value={value}>
                  {unitCollectionLabel(value)}
                </option>
              ))}
            </select>
          </ToolbarFilter>
          <ToolbarFilter label="Age" active={bucket !== ""}>
            <select className="input" value={bucket} onChange={(event) => setBucket(event.target.value)}>
              <option value="">Any age</option>
              {AGING_BUCKETS.map((value) => (
                <option key={value} value={value}>
                  {bucketLabel(value)}
                </option>
              ))}
            </select>
          </ToolbarFilter>
          <ToolbarFilter label="Only show" active={only !== ""}>
            <select className="input" value={only} onChange={(event) => setOnly(event.target.value)}>
              <option value="">Everything</option>
              <option value="overdue">Overdue only</option>
              <option value="unapplied">With unapplied cash</option>
              <option value="disputed">With an open dispute</option>
            </select>
          </ToolbarFilter>
        </DataToolbar>

        <Card flush>
          {rows === null ? (
            <Loading label="Loading the receivables…" shape="rows" />
          ) : view === "accounts" ? (
            visible.length === 0 ? (
              <div className="card-body">
                <EmptyState
                  title={rows.length === 0 ? "Nothing to collect yet" : "No account matches"}
                  hint={
                    rows.length === 0
                      ? "No sale in this project has a payment schedule to collect against."
                      : "Widen the filters to see the rest."
                  }
                />
              </div>
            ) : (
              <TableScroll label="Receivables" fixedFirst>
                <thead>
                  <tr>
                    <th scope="col">Account</th>
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
                    <th scope="col">Next follow-up</th>
                  </tr>
                </thead>
                <tbody>
                  {visible.map((row) => {
                    const code = currencyFor(row);
                    return (
                      <tr key={row.sale_id} aria-selected={open?.sale_id === row.sale_id}>
                        <th scope="row">
                          <button className="button-link" type="button" onClick={() => setOpen(row)}>
                            <IdentityCell name={row.unit_number} meta={row.client_display_name} />
                          </button>
                        </th>
                        <td className="mono">{row.spa_number ?? row.sale_number}</td>
                        <td className="num">{money(row.summary.scheduled_total, code)}</td>
                        <td className="num">{money(row.summary.allocated_total, code)}</td>
                        <td className="num">
                          {isPositive(row.summary.unapplied_cash) ? (
                            <StatusDot tone="warning">{money(row.summary.unapplied_cash, code)}</StatusDot>
                          ) : (
                            money(row.summary.unapplied_cash, code)
                          )}
                        </td>
                        <td className="num">{money(row.summary.outstanding_total, code)}</td>
                        <td className="num">
                          {isPositive(row.summary.overdue_total) ? (
                            <StatusDot tone="danger">{money(row.summary.overdue_total, code)}</StatusDot>
                          ) : (
                            money(row.summary.overdue_total, code)
                          )}
                        </td>
                        <td className="num">
                          {row.summary.oldest_overdue_days > 0 ? `${row.summary.oldest_overdue_days} d` : "—"}
                        </td>
                        <td>
                          <Badge tone={unitCollectionTone(row.summary.derived_collection_status)}>
                            {unitCollectionLabel(row.summary.derived_collection_status)}
                          </Badge>
                          {row.summary.open_disputes > 0 ? (
                            <span className="cell-secondary">{row.summary.open_disputes} disputed, still owed</span>
                          ) : null}
                        </td>
                        <td className="figure">{businessDate(row.summary.next_action_date)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </TableScroll>
            )
          ) : aging === null ? (
            error ? null : <Loading label="Loading the aging…" shape="rows" />
          ) : aging.length === 0 ? (
            <div className="card-body">
              <EmptyState title="Nothing aged" hint={`No overdue receivables as at ${businessDate(asOf)}.`} />
            </div>
          ) : (
            <TableScroll label={`Aging as at ${businessDate(asOf)}`} fixedFirst>
              <thead>
                <tr>
                  <th scope="col">Account</th>
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
                      <th scope="row">
                        <span className="mono">{row.unit_number}</span>
                        <span className="cell-secondary cell-prose">{row.client_display_name}</span>
                      </th>
                      <td>
                        {line.sequence}. {line.label}
                      </td>
                      <td className="figure">{businessDate(line.due_date)}</td>
                      <td className="num">{money(line.scheduled, code)}</td>
                      <td className="num">{money(line.paid, code)}</td>
                      <td className="num">{money(line.outstanding, code)}</td>
                      <td className="num">{line.overdue_days > 0 ? line.overdue_days : "—"}</td>
                      <td>
                        <StatusDot tone={bucketTone(line.bucket)}>{bucketLabel(line.bucket)}</StatusDot>
                      </td>
                      <td>
                        <Badge tone={installmentTone(line.status)}>{installmentLabel(line.status)}</Badge>
                        {line.has_active_waiver ? (
                          <span className="cell-secondary">Collection paused, balance still due</span>
                        ) : null}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </TableScroll>
          )}
        </Card>
      </div>

      {open ? (
        <CollectionAccount
          projectId={projectId}
          saleId={open.sale_id}
          saleNumber={open.sale_number}
          unitNumber={open.unit_number}
          clientName={open.client_display_name}
          currencyCode={currencyFor(open)}
          roles={roles}
          asOf={asOf}
          onClose={() => setOpen(null)}
          onChanged={() => {
            void load();
            if (view === "aging") void loadAging();
          }}
        />
      ) : null}
    </>
  );
}
