"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, paymentPlans, sales } from "@/lib/api";
import type { PlanRegister, SaleContract } from "@/lib/api";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Field,
  FormActions,
  Loading,
  Notice,
  Stat,
  StatRow,
  SubPanel,
  TableScroll,
} from "@/components/ui";
import { useCurrencyCode } from "@/lib/currency";
import { businessDate, money, todayISO } from "@/lib/format";
import { PlanBuilder } from "@/components/projects/payments/PlanBuilder";
import { ReconciliationBadge } from "@/components/projects/payments/ReconciliationStrip";
import { versionLabel, versionTone } from "@/components/projects/payments/labels";

/**
 * The project's payment plans: one line per scheduled sale.
 *
 * Every figure on a row describes the schedule the sale is actually running on.
 * A revision somebody is drafting is named beside it and costs nothing: opening
 * a draft is the start of a conversation, not a change to what the buyer owes,
 * and a register that swapped in the draft's figures would drop a live plan out
 * of the project's active count on the day work began on its successor.
 *
 * Deliberately carries no collected, outstanding, overdue or aged figure. Those
 * are PR-MVP-07's to state; a column of zeroes labelled "paid" would be read as
 * a fact about money rather than the absence of one, and the first person to
 * screenshot it into a board pack would be reporting something untrue.
 *
 * What it does show is whether each schedule reconciles, because a plan that
 * does not is a plan that cannot govern anything.
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
      setError(
        caught instanceof ApiError ? caught.message : "Could not load the payment plans.",
      );
    }
    // Allowed to fail quietly: a reader who may see the register is not always
    // entitled to the contract list, and that should not blank the page.
    try {
      const contracts = await sales.contracts(projectId, {});
      setSchedulable(
        contracts.filter((sale) => ["signature_pending", "active"].includes(sale.status)),
      );
    } catch {
      setSchedulable([]);
    }
  }, [projectId]);

  useEffect(() => {
    void (async () => {
      await load();
    })();
  }, [load]);

  if (projectStatus === "setup") {
    return (
      <Card title="Payment plans" description="Not yet — the project basis is still open.">
        <EmptyState
          title="Finalize project setup"
          hint="Confirm country and currency settings, then move the project to Pre-development."
        />
      </Card>
    );
  }

  if (error && register === null) {
    return (
      <Card title="Payment plans">
        <Notice tone="error">{error}</Notice>
      </Card>
    );
  }

  if (register === null) {
    return (
      <Card title="Payment plans">
        <Loading label="Loading payment plans…" lines={4} />
      </Card>
    );
  }

  // Every count below is over the governing schedules the server named, so a
  // revision in preparation moves none of them.
  const scheduled = register.rows.length;
  const reconciled = register.rows.filter((row) => row.is_reconciled).length;
  const active = register.rows.filter((row) => row.version_status === "active").length;
  const awaiting = register.rows.reduce((total, row) => total + row.awaiting_trigger_count, 0);
  const revising = register.rows.filter((row) => row.revision_version_id !== null).length;
  const unscheduled = schedulable.filter(
    (sale) => !register.rows.some((row) => row.sale_id === sale.id),
  );
  // Only schedules somebody has already agreed to are worth copying, and only
  // the ones this caller can see — the register is already narrowed to those,
  // so the selector inherits the narrowing rather than restating it.
  //
  // The settled version is named on the row by the server rather than inferred
  // from the row's own status: a row describes the version being prepared, so
  // reading the status here would drop a perfectly good standing schedule from
  // the list the moment somebody opened a draft revision of it.
  const copyable = register.rows.filter((row) => row.copy_source_version_id !== null);

  return (
    <>
      <Card
        title="Payment plans"
        description="How each contracted amount is scheduled to be paid, and what makes it due."
        actions={
          canPrepare && unscheduled.length > 0 ? (
            <Button variant="primary" onClick={() => setOpening((open) => !open)}>
              {opening ? "Cancel" : "New payment plan"}
            </Button>
          ) : undefined
        }
      >
        {error ? <Notice tone="error">{error}</Notice> : null}
        {notice ? <Notice tone="success">{notice}</Notice> : null}

        <StatRow>
          <Stat label="Plans" value={scheduled} small />
          <Stat label="Active" value={active} small />
          <Stat label="Reconciled" value={reconciled} small />
          <Stat
            label="Being revised"
            value={revising}
            note="Standing terms unchanged"
            small
          />
          <Stat label="Contracts not yet scheduled" value={unscheduled.length} small />
          <Stat
            label="Instalments awaiting a trigger"
            value={awaiting}
            note="Contracted, not yet due"
            small
          />
        </StatRow>
        <p className="footnote">
          Each row describes the schedule currently governing its sale; a revision being
          prepared is named beside it and changes none of these figures until it is activated.
          A schedule says what the buyer agreed to pay and when. What has actually been paid is
          not recorded yet — that arrives with Collections — so &ldquo;next scheduled&rdquo; is
          the next date still to come on the schedule, and never a statement about arrears.
        </p>

        {opening && canPrepare ? (
          <SubPanel title="Open a payment plan">
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
                      ? {
                          origin_type: "copied_plan",
                          source_version_id: form.source_version_id,
                        }
                      : {}),
                  });
                  setOpening(false);
                  setNotice(`${created.plan.plan_number} opened. Build its schedule next.`);
                  setOpenPlan(created.plan.id);
                  await load();
                } catch (caught) {
                  setError(
                    caught instanceof ApiError
                      ? caught.message
                      : "Could not open the payment plan.",
                  );
                } finally {
                  setBusy(false);
                }
              }}
            >
              <div className="form-grid form-grid-3">
                <Field label="Contract" hint="Only a signed or live contract can be scheduled.">
                  <select
                    className="input"
                    required
                    value={form.sale_contract_id}
                    onChange={(event) =>
                      setForm({ ...form, sale_contract_id: event.target.value })
                    }
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
                <Field
                  label="Start from"
                  hint="Copying brings the shape across. Every amount is re-derived against this contract."
                >
                  <select
                    className="input"
                    value={form.source_version_id}
                    onChange={(event) =>
                      setForm({ ...form, source_version_id: event.target.value })
                    }
                  >
                    <option value="">A blank schedule</option>
                    {copyable.map((row) => (
                      <option key={row.plan_id} value={row.copy_source_version_id ?? ""}>
                        {row.plan_number} · {row.unit_reference} · v
                        {row.copy_source_version_number}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field
                  label="Takes effect"
                  hint="When these terms start governing. Defaults to today."
                >
                  <input
                    className="input input-short"
                    type="date"
                    required
                    value={form.effective_date}
                    onChange={(event) =>
                      setForm({ ...form, effective_date: event.target.value })
                    }
                  />
                </Field>
                <Field
                  label="Reservation"
                  hint="Either way the schedule covers the whole contract."
                >
                  <select
                    className="input"
                    value={form.reservation_treatment}
                    onChange={(event) =>
                      setForm({ ...form, reservation_treatment: event.target.value })
                    }
                  >
                    <option value="reference_only">Held on the deal</option>
                    <option value="included_in_schedule">Shown in the schedule</option>
                  </select>
                </Field>
                <FormActions>
                  <Button variant="primary" type="submit" disabled={busy}>
                    {busy ? "Opening…" : "Open plan"}
                  </Button>
                </FormActions>
              </div>
            </form>
          </SubPanel>
        ) : null}

        {register.rows.length === 0 ? (
          <EmptyState
            title="No payment plans yet"
            hint={
              canPrepare
                ? "Open one against a signed or live contract to schedule what the buyer agreed to pay."
                : "Collections prepares the schedule for each contract."
            }
          />
        ) : (
          <TableScroll label="Payment plan register" fixedFirst>
            <thead>
              <tr>
                <th scope="col">Plan</th>
                <th scope="col">Unit</th>
                <th scope="col">Buyer</th>
                <th scope="col">Contract</th>
                <th scope="col" className="num">
                  Version
                </th>
                <th scope="col">Status</th>
                <th scope="col" className="num">
                  Contract value
                </th>
                <th scope="col" className="num">
                  Instalments
                </th>
                <th scope="col">Schedule</th>
                <th scope="col">Next scheduled</th>
                <th scope="col" className="num">
                  Awaiting
                </th>
                <th scope="col">Open</th>
              </tr>
            </thead>
            <tbody>
              {register.rows.map((row) => (
                <tr key={row.plan_id}>
                  <th scope="row">
                    <button
                      className="button-link mono"
                      type="button"
                      onClick={() => setOpenPlan(row.plan_id)}
                    >
                      {row.plan_number}
                    </button>
                  </th>
                  <td className="mono">{row.unit_reference}</td>
                  <td>{row.client_display_name}</td>
                  <td className="mono">{row.spa_number ?? row.sale_number}</td>
                  <td className="num">{row.version_number ?? "—"}</td>
                  <td>
                    {row.version_status ? (
                      <Badge tone={versionTone(row.version_status)}>
                        {versionLabel(row.version_status)}
                      </Badge>
                    ) : (
                      "—"
                    )}
                    {row.revision_status ? (
                      <>
                        {" "}
                        <span className="subtle nowrap">
                          v{row.revision_version_number} {versionLabel(row.revision_status)}
                        </span>
                      </>
                    ) : null}
                  </td>
                  <td className="num">
                    {money(row.contract_value_covered, currencyCodeOf(row.currency_id))}
                  </td>
                  <td className="num">{row.installment_count}</td>
                  <td>
                    <ReconciliationBadge reconciled={row.is_reconciled} />
                  </td>
                  <td className="mono nowrap">
                    {row.next_scheduled_date === null && row.next_forecast_date === null ? (
                      <span className="subtle">No future date</span>
                    ) : (
                      <>
                        {businessDate(row.next_scheduled_date ?? row.next_forecast_date)}
                        {row.next_scheduled_date === null ? (
                          <>
                            {" "}
                            <span className="subtle">forecast</span>
                          </>
                        ) : null}
                      </>
                    )}
                  </td>
                  <td className="num">{row.awaiting_trigger_count}</td>
                  <td>
                    <Button small onClick={() => setOpenPlan(row.plan_id)}>
                      Open plan
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </TableScroll>
        )}
      </Card>

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
