"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, paymentPlans, sales } from "@/lib/api";
import type { PlanRegister, SaleContract } from "@/lib/api";
import { useCurrencyCode } from "@/lib/currency";
import { businessDate, money, todayISO } from "@/lib/format";
import { sectionDescription } from "@/components/shell/navigation";
import {
  Button,
  Card,
  DataToolbar,
  IdentityCell,
  EmptyState,
  Field,
  FieldRow,
  FormActions,
  Loading,
  Position,
  PositionFigure,
  PositionSupport,
  PositionSupportItem,
  Notice,
  PageHeader,
  StatusDot,
  TableScroll,
  ToolbarFilter,
} from "@/components/ui";
import { PlanBuilder } from "@/components/projects/payments/PlanBuilder";
import { versionLabel, versionTone } from "@/components/projects/payments/labels";

/**
 * The project's payment plans: one line per scheduled sale.
 *
 * Every figure on a row describes the schedule the sale is actually running on.
 * A revision somebody is drafting is named beside it and costs nothing: opening
 * a draft is the start of a conversation, not a change to what the buyer owes.
 *
 * Deliberately carries no collected, outstanding, overdue or aged figure. Those
 * are Collections' to state; a column of zeroes labelled "paid" would be read
 * as a fact about money rather than the absence of one.
 */
export function PaymentPlansTab({
  projectId,
  projectStatus,
  roles,
}: {
  projectId: string;
  projectStatus: string;
  roles: Set<string>;
}) {
  const [register, setRegister] = useState<PlanRegister | null>(null);
  const [schedulable, setSchedulable] = useState<SaleContract[]>([]);
  const [opening, setOpening] = useState(false);
  const [form, setForm] = useState({
    sale_contract_id: "",
    name: "Payment plan",
    reservation_treatment: "reference_only",
    effective_date: todayISO(),
    source_version_id: "",
  });
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [openPlan, setOpenPlan] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const currencyCodeOf = useCurrencyCode();

  const canPrepare = roles.has("collections");

  const load = useCallback(async () => {
    try {
      setRegister(await paymentPlans.register(projectId));
      setError(null);
    } catch (caught) {
      setRegister(null);
      setError(caught instanceof ApiError ? caught.message : "Could not load the payment plans.");
    }
    // Allowed to fail quietly: a reader who may see the register is not always
    // entitled to the contract list, and that should not blank the page.
    try {
      const contracts = await sales.contracts(projectId, {});
      setSchedulable(contracts.filter((sale) => ["signature_pending", "active"].includes(sale.status)));
    } catch {
      setSchedulable([]);
    }
  }, [projectId]);

  useEffect(() => {
    void (async () => {
      if (projectStatus !== "setup") await load();
    })();
  }, [load, projectStatus]);

  const header = (actions?: React.ReactNode) => (
    <PageHeader title="Payment Plans" subtitle={sectionDescription("payments")} compact actions={actions} />
  );

  if (projectStatus === "setup") {
    return (
      <>
        {header()}
        <Card>
          <EmptyState
            title="Finalize project setup first"
            hint="Confirm country and currency settings, then move the project to Pre-development."
          />
        </Card>
      </>
    );
  }

  if (error && register === null) {
    return (
      <>
        {header()}
        <Notice tone="error">{error}</Notice>
      </>
    );
  }

  const rows = register?.rows ?? [];
  // Every count below is over the governing schedules the server named, so a
  // revision in preparation moves none of them. Counting rows is not
  // arithmetic over money; every amount on the page is still the server's.
  const active = rows.filter((row) => row.version_status === "active").length;
  const reconciled = rows.filter((row) => row.is_reconciled).length;
  const revising = rows.filter((row) => row.revision_version_id !== null).length;
  const awaiting = rows.reduce((total, row) => total + row.awaiting_trigger_count, 0);
  const unscheduled = schedulable.filter((sale) => !rows.some((row) => row.sale_id === sale.id));
  // Only schedules somebody has already agreed to are worth copying. The
  // settled version is named on the row by the server rather than inferred
  // from the row's own status.
  const copyable = rows.filter((row) => row.copy_source_version_id !== null);

  const needle = search.trim().toLowerCase();
  const shown = rows.filter((row) => {
    if (status && row.version_status !== status) return false;
    if (
      needle &&
      !`${row.plan_number} ${row.unit_reference} ${row.client_display_name} ${row.sale_number} ${row.spa_number ?? ""}`
        .toLowerCase()
        .includes(needle)
    ) {
      return false;
    }
    return true;
  });
  const filtered = search !== "" || status !== "";

  return (
    <>
      {header(
        canPrepare && unscheduled.length > 0 ? (
          <Button variant="primary" onClick={() => setOpening((open) => !open)} aria-expanded={opening}>
            New payment plan
          </Button>
        ) : undefined,
      )}

      <div className="stack">
        {error ? <Notice tone="error">{error}</Notice> : null}
        {notice ? <Notice tone="success">{notice}</Notice> : null}

        {/* Scheduling, governed. Every figure counts plans and instalments, not
            money received: what a buyer has actually paid is Collections' to
            say, and "next scheduled" is the next date still to come rather
            than any statement about arrears. */}
        <Card
          tone={register ? "command" : undefined}
          title="Scheduled position"
          description={register ? "What is agreed and when it falls due, across this project." : undefined}
        >
          {register === null ? (
            <Loading label="Loading payment plans…" shape="metrics" />
          ) : (
            <>
              <Position compact>
                <PositionFigure lead label="Plans" value={rows.length} />
                <PositionFigure label="Active" value={active} note="Governing a sale" />
                <PositionFigure
                  label="Reconciled"
                  value={reconciled}
                  tone={reconciled < rows.length ? "warning" : "neutral"}
                  note="Cover their contract exactly"
                />
                <PositionFigure
                  label="Not yet scheduled"
                  value={unscheduled.length}
                  tone={unscheduled.length > 0 ? "warning" : "neutral"}
                  note="Contracts without a plan"
                />
              </Position>
              <PositionSupport>
                <PositionSupportItem label="Being revised" value={revising} />
                <PositionSupportItem label="Instalments awaiting a trigger" value={awaiting} />
              </PositionSupport>
            </>
          )}
        </Card>

        {opening && canPrepare ? (
          <Card
            title="Open a payment plan"
            description="Against a signed or live contract. The schedule itself is built next, in the plan's own file."
            actions={<Button variant="quiet" onClick={() => setOpening(false)}>Cancel</Button>}
          >
            <form
              onSubmit={async (event) => {
                event.preventDefault();
                setBusy(true);
                setError(null);
                try {
                  const created = await paymentPlans.create(projectId, {
                    sale_contract_id: form.sale_contract_id,
                    name: form.name,
                    reservation_treatment: form.reservation_treatment,
                    effective_date: form.effective_date,
                    ...(form.source_version_id
                      ? { origin_type: "copied_plan", source_version_id: form.source_version_id }
                      : {}),
                  });
                  setOpening(false);
                  setNotice(`${created.plan.plan_number} opened. Build its schedule next.`);
                  setOpenPlan(created.plan.id);
                  await load();
                } catch (caught) {
                  setError(caught instanceof ApiError ? caught.message : "Could not open the payment plan.");
                } finally {
                  setBusy(false);
                }
              }}
            >
              <FieldRow columns={3}>
                <Field label="Contract" hint="Only a signed or live contract can be scheduled.">
                  <select
                    className="input"
                    required
                    value={form.sale_contract_id}
                    onChange={(event) => setForm({ ...form, sale_contract_id: event.target.value })}
                  >
                    <option value="">Choose a contract</option>
                    {unscheduled.map((sale) => (
                      <option key={sale.id} value={sale.id}>
                        {sale.sale_number}
                        {sale.spa_number ? ` · ${sale.spa_number}` : ""}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Name">
                  <input
                    className="input"
                    required
                    value={form.name}
                    onChange={(event) => setForm({ ...form, name: event.target.value })}
                  />
                </Field>
                <Field label="Start from" hint="Copying brings the shape across. Every amount is re-derived against this contract.">
                  <select
                    className="input"
                    value={form.source_version_id}
                    onChange={(event) => setForm({ ...form, source_version_id: event.target.value })}
                  >
                    <option value="">A blank schedule</option>
                    {copyable.map((row) => (
                      <option key={row.plan_id} value={row.copy_source_version_id ?? ""}>
                        {row.plan_number} · {row.unit_reference} · v{row.copy_source_version_number}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Takes effect" hint="When these terms start governing.">
                  <input
                    className="input input-short"
                    type="date"
                    required
                    value={form.effective_date}
                    onChange={(event) => setForm({ ...form, effective_date: event.target.value })}
                  />
                </Field>
                <Field label="Reservation" hint="Either way the schedule covers the whole contract.">
                  <select
                    className="input"
                    value={form.reservation_treatment}
                    onChange={(event) => setForm({ ...form, reservation_treatment: event.target.value })}
                  >
                    <option value="reference_only">Held on the deal</option>
                    <option value="included_in_schedule">Shown in the schedule</option>
                  </select>
                </Field>
              </FieldRow>
              <FormActions>
                <Button variant="primary" type="submit" disabled={busy}>
                  {busy ? "Opening…" : "Open plan"}
                </Button>
              </FormActions>
            </form>
          </Card>
        ) : null}

        <DataToolbar
          framed
          search={{ value: search, onChange: setSearch, placeholder: "Plan, unit, buyer or contract", label: "Search payment plans" }}
          count={register ? { shown: shown.length, total: register.total, noun: "plan" } : undefined}
          onReset={
            filtered
              ? () => {
                  setSearch("");
                  setStatus("");
                }
              : undefined
          }
        >
          <ToolbarFilter label="Version status">
            <select className="input" value={status} onChange={(event) => setStatus(event.target.value)}>
              <option value="">Any status</option>
              {["draft", "submitted", "approved", "active", "rejected"].map((value) => (
                <option key={value} value={value}>
                  {versionLabel(value)}
                </option>
              ))}
            </select>
          </ToolbarFilter>
        </DataToolbar>

        <Card flush>
          {register === null ? (
            <Loading label="Loading the register…" shape="rows" />
          ) : shown.length === 0 ? (
            <div className="card-body">
              <EmptyState
                title={rows.length === 0 ? "No payment plans yet" : "No plan matches"}
                hint={
                  rows.length === 0
                    ? canPrepare
                      ? "Open one against a signed or live contract to schedule what the buyer agreed to pay."
                      : "Collections prepares the schedule for each contract."
                    : "Widen the filter to see the rest."
                }
              />
            </div>
          ) : (
            <TableScroll label="Payment plan register" fixedFirst>
              <thead>
                <tr>
                  <th scope="col">Plan</th>
                  <th scope="col">Buyer</th>
                  <th scope="col">Contract</th>
                  <th scope="col">Version</th>
                  <th scope="col" className="num">
                    Contract value
                  </th>
                  <th scope="col" className="num">
                    Instalments
                  </th>
                  <th scope="col">Schedule</th>
                  <th scope="col">Next scheduled</th>
                  <th scope="col" className="num">
                    Awaiting trigger
                  </th>
                </tr>
              </thead>
              <tbody>
                {shown.map((row) => (
                  <tr key={row.plan_id}>
                    <th scope="row">
                      <button className="button-link" type="button" onClick={() => setOpenPlan(row.plan_id)}>
                        <IdentityCell name={row.plan_number} meta={row.unit_reference} />
                      </button>
                      <span className="cell-secondary mono">{row.unit_reference}</span>
                    </th>
                    <td className="cell-prose">{row.client_display_name}</td>
                    <td className="mono">{row.spa_number ?? row.sale_number}</td>
                    <td>
                      {row.version_status ? (
                        <StatusDot tone={versionTone(row.version_status)}>
                          v{row.version_number} · {versionLabel(row.version_status)}
                        </StatusDot>
                      ) : (
                        <span className="muted">—</span>
                      )}
                      {row.revision_status ? (
                        <span className="cell-secondary">
                          v{row.revision_version_number} {versionLabel(row.revision_status).toLowerCase()} in preparation
                        </span>
                      ) : null}
                    </td>
                    <td className="num">{money(row.contract_value_covered, currencyCodeOf(row.currency_id))}</td>
                    <td className="num">{row.installment_count}</td>
                    <td>
                      {row.is_reconciled ? (
                        <StatusDot tone="success">Reconciled</StatusDot>
                      ) : (
                        <StatusDot tone="warning">Does not reconcile</StatusDot>
                      )}
                    </td>
                    <td className="figure">
                      {row.next_scheduled_date === null && row.next_forecast_date === null ? (
                        <span className="muted">No future date</span>
                      ) : (
                        <>
                          {businessDate(row.next_scheduled_date ?? row.next_forecast_date)}
                          {row.next_scheduled_date === null ? <span className="cell-secondary">forecast</span> : null}
                        </>
                      )}
                    </td>
                    <td className="num">{row.awaiting_trigger_count}</td>
                  </tr>
                ))}
              </tbody>
            </TableScroll>
          )}
        </Card>
      </div>

      {openPlan ? (
        <PlanBuilder
          projectId={projectId}
          planId={openPlan}
          roles={roles}
          onClose={() => setOpenPlan(null)}
          onChanged={load}
        />
      ) : null}
    </>
  );
}
