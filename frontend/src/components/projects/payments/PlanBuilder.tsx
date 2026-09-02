"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, paymentPlans } from "@/lib/api";
import type { PaymentPlanDetail, PlanInstallment, PlanVersionDetail } from "@/lib/api";
import {
  Badge,
  Button,
  ButtonRow,
  Drawer,
  EmptyState,
  Field,
  FieldRow,
  FormActions,
  FormDialog,
  KeyValue,
  KeyValueGrid,
  Loading,
  Notice,
  PromptDialog,
  SectionHeader,
  Steps,
  SubPanel,
  TableScroll,
} from "@/components/ui";
import type { DrawerFact } from "@/components/ui";
import { useCurrencyCode } from "@/lib/currency";
import { businessDate, fractionFromPercent, money, todayISO } from "@/lib/format";
import { ReconciliationStrip } from "@/components/projects/payments/ReconciliationStrip";
import {
  ScheduleEditor,
  ScheduleTable,
  emptyRow,
  rowFrom,
} from "@/components/projects/payments/ScheduleEditor";
import type { DraftRow } from "@/components/projects/payments/ScheduleEditor";
import {
  VERSION_SEQUENCE,
  allocationLabel,
  chargeLabel,
  originLabel,
  reservationTreatmentLabel,
  triggerLabel,
  versionLabel,
  versionTone,
} from "@/components/projects/payments/labels";

/** Triggers the calendar settles on its own; everything else waits on an event. */
const DATE_TRIGGERS = new Set([
  "fixed_date",
  "days_after_spa",
  "recurring_monthly",
  "recurring_quarterly",
]);

/** What each attestation state is called in front of somebody deciding on it. */
const ATTESTATION_LABELS: Record<string, string> = {
  submitted: "Awaiting approval",
  approved: "Approved",
  reversed: "Withdrawn",
};

/** A blank attestation. The date is left to the person who witnessed the event. */
function emptyAttestation() {
  return { event_date: "", evidence_reference: "", reason: "" };
}

type Ask = {
  title: string;
  label: string;
  hint?: string;
  confirmLabel: string;
  run: (value: string) => void;
};

/**
 * The payment plan builder: one sale's schedule, in the state it is in.
 *
 * A draft is editable as a grid, because a schedule is negotiated as a whole —
 * changing one instalment changes what every other is worth. Once it has been
 * put forward it becomes a read-only table, because from that point the way to
 * change a contractual term is a new version, not an edit.
 *
 * The reconciliation strip is the server's, always. This component never sums a
 * column, never turns a percentage into an amount and never decides whether the
 * plan adds up: the gate that refuses activation uses the backend's arithmetic,
 * and a second implementation here would eventually disagree with it in front
 * of an operator who cannot see why.
 */
export function PlanBuilder({
  projectId,
  planId,
  roles,
  onClose,
  onChanged,
}: {
  projectId: string;
  planId: string;
  roles: Set<string>;
  onClose: () => void;
  onChanged: () => Promise<void>;
}) {
  const [detail, setDetail] = useState<PaymentPlanDetail | null>(null);
  const [rows, setRows] = useState<DraftRow[]>([]);
  const [allocationMode, setAllocationMode] = useState("percentage");
  const [chargeMode, setChargeMode] = useState("pro_rata");
  const [section, setSection] = useState("schedule");
  const [series, setSeries] = useState({
    frequency: "recurring_monthly",
    first_due_date: "",
    count: "12",
    label_prefix: "Instalment",
  });
  const [seriesOpen, setSeriesOpen] = useState(false);
  const [ask, setAsk] = useState<Ask | null>(null);
  const [attesting, setAttesting] = useState<PlanInstallment | null>(null);
  const [attestation, setAttestation] = useState(emptyAttestation());
  const [revising, setRevising] = useState(false);
  const [revision, setRevision] = useState({ change_reason: "", effective_date: "" });
  // Which version the drawer is showing. Null means the one being prepared;
  // any other id selects a version to read. Selecting one changes nothing on
  // the server — it is a choice of which immutable record to look at.
  const [showing, setShowing] = useState<string | null>(null);
  const [historical, setHistorical] = useState<PlanVersionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const currencyCodeOf = useCurrencyCode();

  const canPrepare = roles.has("collections");
  const canApprove = roles.has("approver_cfo");

  const load = useCallback(async () => {
    try {
      const body = await paymentPlans.read(projectId, planId);
      setDetail(body);
      if (body.current) {
        setAllocationMode(body.current.version.allocation_mode);
        setChargeMode(body.current.version.charge_allocation_mode);
        setRows(body.current.installments.map(rowFrom));
      }
      setError(null);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not load the payment plan.");
    }
  }, [projectId, planId]);

  useEffect(() => {
    void (async () => {
      await load();
    })();
  }, [load]);

  // A version that is neither in preparation nor governing is read on demand.
  // The plan response already carries those two in full, so the only request
  // ever made here is for history somebody deliberately opened.
  useEffect(() => {
    if (showing === null || detail === null) return;
    if (showing === detail.current?.version.id || showing === detail.active?.version.id) return;
    void (async () => {
      try {
        setHistorical(await paymentPlans.version(projectId, planId, showing));
      } catch (caught) {
        setError(caught instanceof ApiError ? caught.message : "Could not load that version.");
      }
    })();
  }, [showing, detail, projectId, planId]);

  const run = async (action: () => Promise<unknown>, done: string) => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await action();
      setNotice(done);
      setShowing(null);
      await load();
      await onChanged();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "That did not work.");
    } finally {
      setBusy(false);
    }
  };

  const askThen = (
    prompt: Omit<Ask, "run">,
    action: (value: string) => Promise<unknown>,
    done: string,
  ) => {
    setAsk({
      ...prompt,
      run: (value) => {
        setAsk(null);
        void run(() => action(value), done);
      },
    });
  };

  const change = (key: string, field: keyof DraftRow, value: string) => {
    setRows((current) =>
      current.map((row) => (row.key === key ? { ...row, [field]: value } : row)),
    );
  };

  const remove = (key: string) => {
    setRows((current) =>
      current
        .filter((row) => row.key !== key)
        .map((row, index) => ({ ...row, sequence: index + 1 })),
    );
  };

  const addRow = () => setRows((current) => [...current, emptyRow(current.length + 1)]);

  const addSeries = async () => {
    setBusy(true);
    setError(null);
    try {
      const preview = await paymentPlans.seriesPreview(projectId, {
        frequency: series.frequency,
        first_due_date: series.first_due_date,
        count: Number(series.count),
        label_prefix: series.label_prefix,
      });
      setRows((current) => [
        ...current,
        ...preview.rows.map((row, index) => ({
          ...emptyRow(current.length + index + 1),
          label: row.label,
          trigger_type: series.frequency,
          contractual_due_date: row.due_date,
        })),
      ]);
      setSeriesOpen(false);
      setNotice(`${preview.rows.length} dates added. Set what each one is worth, then save.`);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not propose those dates.");
    } finally {
      setBusy(false);
    }
  };

  const saveSchedule = async (versionId: string) => {
    await run(
      () =>
        paymentPlans.writeSchedule(projectId, planId, versionId, {
          allocation_mode: allocationMode,
          charge_allocation_mode: chargeMode,
          installments: rows.map((row) => ({
            sequence: row.sequence,
            label: row.label,
            trigger_type: row.trigger_type,
            ...(row.trigger_reference ? { trigger_reference: row.trigger_reference } : {}),
            ...(row.offset_days ? { offset_days: Number(row.offset_days) } : {}),
            ...(row.contractual_due_date
              ? { contractual_due_date: row.contractual_due_date }
              : {}),
            ...(row.forecast_due_date ? { forecast_due_date: row.forecast_due_date } : {}),
            grace_days: Number(row.grace_days || "0"),
            ...(allocationMode === "percentage"
              ? { principal_fraction: fractionFromPercent(row.principal_fraction) }
              : { principal_amount: row.principal_amount }),
            ...(chargeMode === "manual"
              ? { tax_amount: row.tax_amount || "0.00", fee_amount: row.fee_amount || "0.00" }
              : {}),
          })),
        }),
      "Schedule saved.",
    );
  };

  if (error && detail === null) {
    return (
      <Drawer eyebrow="Payment plan" title="Payment plan" onClose={onClose}>
        <Notice tone="error">{error}</Notice>
      </Drawer>
    );
  }
  if (detail === null) {
    return (
      <Drawer eyebrow="Payment plan" title="Loading the payment plan…" onClose={onClose}>
        <Loading label="Loading the payment plan…" shape="page" />
      </Drawer>
    );
  }

  const current = detail.current;
  const active = detail.active;
  // Two versions can be true at once: the one being prepared and the one the
  // buyer is actually being held to. They are the same most of the time, and
  // during a revision — which can run for weeks — they are not.
  const revisionOpen = Boolean(current && active && current.version.id !== active.version.id);
  // A previously fetched version is only used when it is the one asked for,
  // so no stale schedule can be shown while the next one is on its way — which
  // is also why the effect above never has to clear it.
  const shownDetail =
    showing === null || showing === current?.version.id
      ? current
      : showing === active?.version.id
        ? active
        : historical?.version.id === showing
          ? historical
          : null;
  const version = shownDetail?.version ?? null;
  const isCurrent = Boolean(version && current && version.id === current.version.id);
  const isActive = Boolean(version && active && version.id === active.version.id);
  const isHistory = Boolean(version && !isCurrent && !isActive);
  // Only the version in preparation is editable, and only while it is a draft.
  const isDraft = isCurrent && version?.status === "draft";
  const code = currencyCodeOf(detail.currency_id);
  const sections = [
    { key: "schedule", label: "Schedule" },
    { key: "terms", label: "Terms" },
    { key: "history", label: "History" },
  ];

  /**
   * Whether cash has been confirmed against this plan.
   *
   * Once it has, PR-MVP-07 refuses the ordinary activation of a replacement
   * schedule: the new instalments have new identifiers, and every allocation
   * already made points at the old ones, so activating here would make
   * collected money vanish from the current view. The restructure carries them
   * across in the same transaction, which is why the way through is there and
   * not here.
   *
   * The button is hidden rather than disabled and the reason is written out.
   * A disabled control with no explanation is the thing this replaces.
   */
  const collectionsStarted = detail.plan.collections_started_at !== null;

  // The figures every reader opens a plan for. All four are the version's own
  // frozen basis and the server's reconciliation of the schedule against it.
  const facts: DrawerFact[] = [
    { label: "Contract principal", value: money(version?.contract_value_covered ?? null, code) },
    { label: "Total buyer payable", value: money(version?.total_buyer_payable_snapshot ?? null, code) },
    {
      label: "Instalments",
      value: shownDetail ? shownDetail.reconciliation.installment_count : "—",
      note: shownDetail
        ? shownDetail.reconciliation.is_reconciled
          ? "Reconciled"
          : "Does not reconcile"
        : undefined,
    },
    { label: "Takes effect", value: businessDate(version?.effective_date) },
  ];

  return (
    <Drawer
      eyebrow="Payment plan"
      title={detail.plan.plan_number}
      subtitle={`${detail.unit_reference} · ${detail.sale_number} · ${detail.client_display_name}`}
      meta={
        <>
          {version ? (
            <Badge tone={versionTone(version.status)}>
              v{version.version_number} · {versionLabel(version.status)}
            </Badge>
          ) : null}
          {active && version && active.version.id !== version.id ? (
            <Badge tone="success">
              v{active.version.version_number} governs this sale
            </Badge>
          ) : null}
          {collectionsStarted ? <Badge tone="info">Collections started</Badge> : null}
        </>
      }
      facts={facts}
      tabs={sections}
      activeTab={section}
      onSelectTab={setSection}
      onClose={onClose}
    >
      {error ? <Notice tone="error">{error}</Notice> : null}
      {notice ? <Notice tone="success">{notice}</Notice> : null}

      {section === "schedule" && shownDetail && version ? (
        <>
          {revisionOpen && current && active ? (
            <section>
              <SectionHeader
                title="Two schedules"
                description="One is being prepared. The other is the one this buyer is being held to until the revision is activated."
              />
              <div className="version-switch" role="group" aria-label="Which version to show">
                <Button
                  variant={isCurrent ? "primary" : "quiet"}
                  aria-pressed={isCurrent}
                  onClick={() => setShowing(current.version.id)}
                >
                  In preparation · v{current.version.version_number} ·{" "}
                  {versionLabel(current.version.status)}
                </Button>
                <Button
                  variant={isActive ? "primary" : "quiet"}
                  aria-pressed={isActive}
                  onClick={() => setShowing(active.version.id)}
                >
                  Standing schedule · v{active.version.version_number} · Governs this sale
                </Button>
              </div>
              <p className="footnote">
                Opening a revision does not change what the buyer owes. Instalments on the
                standing schedule keep falling due, and attestations against it can still be
                made and decided, until the revision is activated.
              </p>
            </section>
          ) : null}

          {isHistory ? (
            <Notice tone="info">
              Reading version {version.version_number} as it stands. Nothing here can be
              changed — a superseded schedule is the record of what governed, and it is kept
              exactly as it was.{" "}
              <button
                className="button-link"
                type="button"
                onClick={() => setShowing(null)}
              >
                Back to the current version
              </button>
            </Notice>
          ) : null}

          <section>
            <SectionHeader
              title={
                isActive && revisionOpen
                  ? "The standing schedule"
                  : isHistory
                    ? "Where this version ended"
                    : "Where this version stands"
              }
            />
            <Steps
              label="Payment plan lifecycle"
              steps={VERSION_SEQUENCE.map((key) => ({
                key,
                label: versionLabel(key),
                state:
                  key === version.status
                    ? "current"
                    : VERSION_SEQUENCE.indexOf(key) < VERSION_SEQUENCE.indexOf(version.status)
                      ? "done"
                      : "pending",
              }))}
            />
            {version.status === "rejected" ? (
              <Notice tone="error">
                Refused: {version.rejection_reason}. Create a new version to revise the terms.
              </Notice>
            ) : null}
            {version.status === "superseded" ? (
              <Notice tone="info">
                Superseded. This is the schedule that governed the sale until it was replaced.
              </Notice>
            ) : null}
          </section>

          <section>
            <SectionHeader
              title="Reconciliation"
              description="Computed by the server from the stored schedule. Nothing here is totalled in the browser."
            />
            <ReconciliationStrip
              reconciliation={shownDetail.reconciliation}
              currencyId={detail.currency_id}
            />
          </section>

          <section>
            <SectionHeader
              title="Instalments"
              description={
                isDraft
                  ? "Edit the whole schedule and save it in one go."
                  : "Frozen. A contractual change is a new version, not an edit."
              }
              actions={
                isDraft && canPrepare ? (
                  <>
                    <Button small onClick={addRow}>
                      Add instalment
                    </Button>
                    <Button small onClick={() => setSeriesOpen((open) => !open)}>
                      {seriesOpen ? "Cancel series" : "Add a series"}
                    </Button>
                  </>
                ) : undefined
              }
            />

            {isDraft && canPrepare && seriesOpen ? (
              <SubPanel title="Add a recurring series">
                <p className="section-description">
                  Proposes the dates only. What each instalment is worth stays with the
                  allocation mode below.
                </p>
                <FieldRow columns={4}>
                  <Field label="Frequency">
                    <select
                      className="input"
                      value={series.frequency}
                      onChange={(event) =>
                        setSeries({ ...series, frequency: event.target.value })
                      }
                    >
                      <option value="recurring_monthly">Monthly</option>
                      <option value="recurring_quarterly">Quarterly</option>
                    </select>
                  </Field>
                  <Field label="First due date">
                    <input
                      className="input"
                      type="date"
                      value={series.first_due_date}
                      onChange={(event) =>
                        setSeries({ ...series, first_due_date: event.target.value })
                      }
                    />
                  </Field>
                  <Field label="How many" hint="A four-year plan is 48.">
                    <input
                      className="input"
                      inputMode="numeric"
                      value={series.count}
                      onChange={(event) => setSeries({ ...series, count: event.target.value })}
                    />
                  </Field>
                  <Field label="Label prefix">
                    <input
                      className="input"
                      value={series.label_prefix}
                      onChange={(event) =>
                        setSeries({ ...series, label_prefix: event.target.value })
                      }
                    />
                  </Field>
                </FieldRow>
                <FormActions>
                  <Button
                    variant="primary"
                    disabled={busy || !series.first_due_date}
                    onClick={() => void addSeries()}
                  >
                    Add these dates
                  </Button>
                </FormActions>
              </SubPanel>
            ) : null}

            {isDraft && canPrepare ? (
              <>
                <FieldRow columns={2}>
                  <Field
                    label="Allocation"
                    hint="Whichever you choose, the server derives the other."
                  >
                    <select
                      className="input"
                      value={allocationMode}
                      onChange={(event) => setAllocationMode(event.target.value)}
                    >
                      <option value="percentage">{allocationLabel("percentage")}</option>
                      <option value="amount">{allocationLabel("amount")}</option>
                    </select>
                  </Field>
                  <Field label="Tax and buyer fees">
                    <select
                      className="input"
                      value={chargeMode}
                      onChange={(event) => setChargeMode(event.target.value)}
                    >
                      <option value="pro_rata">{chargeLabel("pro_rata")}</option>
                      <option value="manual">{chargeLabel("manual")}</option>
                    </select>
                  </Field>
                </FieldRow>
                {rows.length === 0 ? (
                  <EmptyState
                    title="No instalments yet"
                    hint="Add one at a time, or generate a monthly or quarterly series."
                    actions={
                      <Button variant="primary" onClick={addRow}>
                        Add the first instalment
                      </Button>
                    }
                  />
                ) : (
                  <ScheduleEditor
                    rows={rows}
                    allocationMode={allocationMode}
                    chargeMode={chargeMode}
                    currencyId={detail.currency_id}
                    onChange={change}
                    onRemove={remove}
                  />
                )}
                <FormActions>
                  <Button
                    variant="primary"
                    disabled={busy || rows.length === 0}
                    onClick={() => void saveSchedule(version.id)}
                  >
                    {busy ? "Saving…" : "Save schedule"}
                  </Button>
                </FormActions>
              </>
            ) : shownDetail.installments.length === 0 ? (
              <EmptyState title="No instalments" hint="This version has no schedule." />
            ) : (
              <ScheduleTable
                installments={shownDetail.installments}
                currencyId={detail.currency_id}
              />
            )}
          </section>

          <section>
            <SectionHeader title="What happens next" />
            <ButtonRow>
              {canPrepare && isCurrent && isDraft ? (
                <Button
                  variant="primary"
                  disabled={busy || !shownDetail.reconciliation.is_reconciled}
                  onClick={() =>
                    void run(
                      () => paymentPlans.submitVersion(projectId, planId, version.id),
                      "Put forward for approval.",
                    )
                  }
                >
                  Submit for approval
                </Button>
              ) : null}
              {canApprove && isCurrent && version.status === "submitted" ? (
                <>
                  <Button
                    variant="primary"
                    disabled={busy}
                    onClick={() =>
                      askThen(
                        {
                          title: "Approve this schedule",
                          label: "Why is this approved?",
                          confirmLabel: "Approve",
                        },
                        (reason) =>
                          paymentPlans.approveVersion(projectId, planId, version.id, reason),
                        "Approved. Activate it to make it the governing schedule.",
                      )
                    }
                  >
                    Approve
                  </Button>
                  <Button
                    variant="danger"
                    disabled={busy}
                    onClick={() =>
                      askThen(
                        {
                          title: "Refuse this schedule",
                          label: "Why is this refused?",
                          confirmLabel: "Refuse",
                        },
                        (reason) =>
                          paymentPlans.rejectVersion(projectId, planId, version.id, reason),
                        "Refused. A revision is a new version.",
                      )
                    }
                  >
                    Refuse
                  </Button>
                </>
              ) : null}
              {canApprove && isCurrent && version.status === "approved" && !collectionsStarted ? (
                <Button
                  variant="primary"
                  disabled={busy}
                  onClick={() =>
                    void run(
                      () => paymentPlans.activateVersion(projectId, planId, version.id),
                      "Active. This is now the schedule governing the sale.",
                    )
                  }
                >
                  Activate
                </Button>
              ) : null}
              {isCurrent && version.status === "approved" && collectionsStarted ? (
                <Notice tone="info">
                  This plan has confirmed collection activity, so the schedule cannot be swapped
                  out from here. Apply it through a Collections restructure, which carries the
                  cash already received onto the new instalments in the same transaction.
                </Notice>
              ) : null}
              {canPrepare && isActive ? (
                <>
                  {revisionOpen ? null : (
                    <Button
                      disabled={busy}
                      onClick={() => {
                        setRevision({ change_reason: "", effective_date: todayISO() });
                        setRevising(true);
                      }}
                    >
                      Revise
                    </Button>
                  )}
                  <Button
                    disabled={busy}
                    onClick={() =>
                      void run(async () => {
                        const result = await paymentPlans.refreshTriggers(projectId, planId);
                        setNotice(
                          `${result.triggered.length} instalment(s) triggered; ` +
                            `${result.still_awaiting.length} still awaiting.`,
                        );
                      }, "Triggers refreshed.")
                    }
                  >
                    Refresh triggers
                  </Button>
                </>
              ) : null}
            </ButtonRow>
            {isDraft && !shownDetail.reconciliation.is_reconciled ? (
              <p className="footnote">
                A schedule can only be put forward once it covers the contract exactly.
              </p>
            ) : null}
          </section>

          {!isDraft ? (
            <ContingentSection
              installments={shownDetail.installments}
              governing={isActive}
              canPrepare={canPrepare && isActive}
              canApprove={canApprove && isActive}
              busy={busy}
              onAttest={(row) => {
                setAttestation(emptyAttestation());
                setAttesting(row);
              }}
              onApprove={(eventId) =>
                void run(
                  () => paymentPlans.approveManualTrigger(projectId, planId, eventId),
                  "Attestation approved. The instalment is now due.",
                )
              }
              onReverse={(eventId) =>
                askThen(
                  {
                    title: "Withdraw this attestation",
                    label: "Why is it being withdrawn?",
                    hint: "The attestation stays on the record. The instalment goes back to waiting.",
                    confirmLabel: "Withdraw",
                  },
                  (reason) => paymentPlans.reverseManualTrigger(projectId, planId, eventId, reason),
                  "Withdrawn. The instalment is waiting on its trigger again.",
                )
              }
            />
          ) : null}
        </>
      ) : null}

      {section === "schedule" && !shownDetail ? (
        showing === null ? (
          <EmptyState title="No version" hint="This plan has no schedule yet." />
        ) : (
          <Loading label="Loading that version…" shape="rows" rows={4} />
        )
      ) : null}

      {section === "terms" && version ? (
        <section>
          <SectionHeader
            title="Basis"
            description="Frozen from the contract when this version was created. Never recomputed."
          />
          <KeyValueGrid columns={3}>
            <KeyValue label="Contract principal" mono value={money(version.contract_value_covered, code)} />
            <KeyValue label="Tax" mono value={money(version.tax_total_snapshot, code)} />
            <KeyValue label="Buyer fees" mono value={money(version.buyer_fee_total_snapshot, code)} />
            <KeyValue
              label="Total buyer payable"
              mono
              value={money(version.total_buyer_payable_snapshot, code)}
            />
            <KeyValue label="Allocation" value={allocationLabel(version.allocation_mode)} />
            <KeyValue label="Tax and fees" value={chargeLabel(version.charge_allocation_mode)} />
            <KeyValue
              label="Reservation"
              value={reservationTreatmentLabel(version.reservation_treatment)}
            />
            <KeyValue label="Origin" value={originLabel(version.origin_type)} />
            <KeyValue label="Takes effect" mono value={businessDate(version.effective_date)} />
            <KeyValue label="SPA" mono value={detail.spa_number} />
            <KeyValue label="Sale status" value={detail.sale_status.replace("_", " ")} />
            <KeyValue label="Change reason" value={version.change_reason} />
          </KeyValueGrid>
          <p className="footnote">
            A confirmed deposit or first-payment gate on the contract attests that evidence
            exists. It is not a receipt, and it is never subtracted from this schedule.
          </p>
        </section>
      ) : null}

      {section === "history" ? (
        <section>
          <SectionHeader
            title="Versions"
            description="Every schedule this plan has had. Open one to read it exactly as it stood."
          />
          <TableScroll label="Plan versions" compact>
            <thead>
              <tr>
                <th scope="col">Version</th>
                <th scope="col">Status</th>
                <th scope="col">Takes effect</th>
                <th scope="col">Standing</th>
                <th scope="col">
                  <span className="visually-hidden">Open</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {detail.versions.map((entry) => (
                <tr key={entry.id}>
                  <th scope="row" className="mono">
                    v{entry.version_number}
                  </th>
                  <td>
                    <Badge tone={versionTone(entry.status)}>{versionLabel(entry.status)}</Badge>
                  </td>
                  <td className="figure">{businessDate(entry.effective_date)}</td>
                  <td>
                    {entry.id === detail.active?.version.id
                      ? "Governs this sale"
                      : entry.id === detail.current?.version.id
                        ? "In preparation"
                        : "—"}
                  </td>
                  <td>
                    <Button
                      small
                      variant="quiet"
                      onClick={() => {
                        setShowing(entry.id);
                        setSection("schedule");
                      }}
                    >
                      View
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </TableScroll>
          <p className="footnote">
            Nothing is overwritten. A superseded schedule stays readable exactly as it governed,
            and opening one changes nothing about which schedule the sale runs on.
          </p>
        </section>
      ) : null}

      {attesting ? (
        <FormDialog
          title={`Attest that ${attesting.label} occurred`}
          description="This records an event that has already happened. An Approver / CFO must sanction it before the amount falls due."
          confirmLabel="Submit attestation"
          busy={busy}
          disabled={
            !attestation.event_date ||
            !attestation.evidence_reference.trim() ||
            !attestation.reason.trim()
          }
          onCancel={() => setAttesting(null)}
          onSubmit={() => {
            const row = attesting;
            const entered = attestation;
            setAttesting(null);
            void run(
              () =>
                paymentPlans.submitManualTrigger(projectId, planId, row.id, {
                  event_date: entered.event_date,
                  evidence_reference: entered.evidence_reference.trim(),
                  reason: entered.reason.trim(),
                }),
              "Attestation submitted for approval.",
            );
          }}
        >
          <Field
            label="Event date"
            hint="The day it actually happened. It cannot be in the future."
          >
            <input
              className="input"
              type="date"
              required
              max={todayISO()}
              value={attestation.event_date}
              onChange={(event) =>
                setAttestation({ ...attestation, event_date: event.target.value })
              }
            />
          </Field>
          <Field label="Evidence reference" hint="The document or record that proves it.">
            <input
              className="input"
              required
              value={attestation.evidence_reference}
              onChange={(event) =>
                setAttestation({ ...attestation, evidence_reference: event.target.value })
              }
            />
          </Field>
          <Field label="Reason" hint="What an approver needs to know to sanction this.">
            <input
              className="input"
              required
              value={attestation.reason}
              onChange={(event) => setAttestation({ ...attestation, reason: event.target.value })}
            />
          </Field>
        </FormDialog>
      ) : null}

      {revising ? (
        <FormDialog
          title="Revise this plan"
          description="The standing schedule keeps governing the sale until the revision is approved and activated."
          confirmLabel="Open a revision"
          busy={busy}
          disabled={!revision.change_reason.trim() || !revision.effective_date}
          onCancel={() => setRevising(false)}
          onSubmit={() => {
            const entered = revision;
            setRevising(false);
            void run(
              () =>
                paymentPlans.createVersion(projectId, planId, {
                  change_reason: entered.change_reason.trim(),
                  effective_date: entered.effective_date,
                }),
              "Revision opened. The current schedule still governs the sale.",
            );
          }}
        >
          <Field label="Why are the terms changing?">
            <input
              className="input"
              required
              value={revision.change_reason}
              onChange={(event) =>
                setRevision({ ...revision, change_reason: event.target.value })
              }
            />
          </Field>
          <Field
            label="Takes effect"
            hint="A future date can be approved now and activated when it arrives."
          >
            <input
              className="input"
              type="date"
              required
              value={revision.effective_date}
              onChange={(event) =>
                setRevision({ ...revision, effective_date: event.target.value })
              }
            />
          </Field>
        </FormDialog>
      ) : null}

      {ask ? (
        <PromptDialog
          title={ask.title}
          label={ask.label}
          hint={ask.hint}
          confirmLabel={ask.confirmLabel}
          busy={busy}
          onSubmit={ask.run}
          onCancel={() => setAsk(null)}
        />
      ) : null}
    </Drawer>
  );
}

/**
 * The contingent instalments, and the attestations made about them.
 *
 * A construction milestone is listed but has no action: PR-MVP-09 certifies
 * those, and offering a button that claimed to would be the system inventing a
 * certificate.
 *
 * The attestations arrive on the instalment rows themselves, from the same
 * response that drew the schedule. That is the only reason an approver can see
 * a whole plan's pending decisions at once without the screen making a request
 * per instalment — which on a hundred-row schedule would make the plans with
 * the most to decide the slowest to open.
 */
function ContingentSection({
  installments,
  governing,
  canPrepare,
  canApprove,
  busy,
  onAttest,
  onApprove,
  onReverse,
}: {
  installments: PlanInstallment[];
  /** Whether this is the schedule the sale actually runs on. */
  governing: boolean;
  canPrepare: boolean;
  canApprove: boolean;
  busy: boolean;
  onAttest: (row: PlanInstallment) => void;
  onApprove: (eventId: string) => void;
  onReverse: (eventId: string) => void;
}) {
  const contingent = installments.filter(
    (row) => !DATE_TRIGGERS.has(row.trigger_type) || row.trigger_events.length > 0,
  );
  if (contingent.length === 0) return null;

  return (
    <section>
      <SectionHeader
        title={governing ? "Waiting on an event" : "Events and attestations"}
        description={
          governing
            ? "These amounts are contracted. What makes each one due has not happened yet, and a forecast date is not the event."
            : "What each contingent instalment waited on, and every attestation ever made about it. This version does not govern the sale, so there is nothing to decide here."
        }
      />
      {contingent.map((row) => {
        const standing = row.trigger_events.find((event) => event.status === "submitted");
        return (
          <div key={row.id} className="contingent-row">
            <div className="contingent-head">
              <span className="chip-label">#{row.sequence}</span>
              <strong>{row.label}</strong>
              <span className="chip-label">{triggerLabel(row.trigger_type)}</span>
              {row.trigger_status === "triggered" ? (
                <Badge tone="success">Due {businessDate(row.actual_due_date)}</Badge>
              ) : (
                <Badge tone="warning">Awaiting its trigger</Badge>
              )}
              {row.trigger_type === "construction_milestone" ? (
                <span className="chip-label">Awaiting certification</span>
              ) : null}
              {row.trigger_type === "manual_approved_event" &&
              canPrepare &&
              !standing &&
              row.trigger_status !== "triggered" ? (
                <Button small variant="quiet" disabled={busy} onClick={() => onAttest(row)}>
                  Attest
                </Button>
              ) : null}
            </div>

            {row.trigger_events.map((event) => (
              <div key={event.id} className="attestation">
                <Badge
                  tone={
                    event.status === "approved"
                      ? "success"
                      : event.status === "reversed"
                        ? "neutral"
                        : "warning"
                  }
                >
                  {ATTESTATION_LABELS[event.status] ?? event.status}
                </Badge>
                <span className="chip-label">Occurred</span>
                <strong className="mono nowrap">{businessDate(event.event_date)}</strong>
                <span className="chip-label">Evidence</span>
                <strong className="mono">{event.evidence_reference}</strong>
                <p className="attestation-reason">{event.reason}</p>
                {event.status === "reversed" && event.reversal_reason ? (
                  <p className="attestation-reason">Withdrawn: {event.reversal_reason}</p>
                ) : null}
                {canApprove && event.status === "submitted" ? (
                  <Button
                    small
                    variant="primary"
                    disabled={busy}
                    onClick={() => onApprove(event.id)}
                  >
                    Approve trigger
                  </Button>
                ) : null}
                {canApprove && event.status === "approved" ? (
                  <Button
                    small
                    variant="danger"
                    disabled={busy}
                    onClick={() => onReverse(event.id)}
                  >
                    Reverse
                  </Button>
                ) : null}
              </div>
            ))}

            {governing &&
            row.trigger_type === "manual_approved_event" &&
            row.trigger_events.length === 0 &&
            !canPrepare ? (
              <p className="footnote">
                Collections attests that this event occurred; an Approver / CFO sanctions it.
              </p>
            ) : null}
            {governing && standing && !canApprove ? (
              <p className="footnote">
                Submitted, and waiting on an Approver / CFO. Nothing is due until they sanction
                it.
              </p>
            ) : null}
          </div>
        );
      })}
      {governing ? (
        <p className="footnote">
          A construction milestone becomes due when construction certifies it, which this system
          does not yet record. Handover and title transfer resolve from the sale itself — use
          Refresh triggers once the event has happened.
        </p>
      ) : null}
    </section>
  );
}
