"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, paymentPlans } from "@/lib/api";
import type { PaymentPlanDetail, PlanInstallment } from "@/lib/api";
import {
  Badge,
  Button,
  ButtonRow,
  Drawer,
  EmptyState,
  Field,
  FormActions,
  KeyValue,
  KeyValueGrid,
  Loading,
  Notice,
  PromptDialog,
  SectionHeader,
  Steps,
  SubPanel,
} from "@/components/ui";
import { useCurrencyCode } from "@/lib/currency";
import { businessDate, money } from "@/lib/format";
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

  const run = async (action: () => Promise<unknown>, done: string) => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await action();
      setNotice(done);
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
              ? { principal_fraction: row.principal_fraction }
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
      <Drawer title="Payment plan" onClose={onClose}>
        <Notice tone="error">{error}</Notice>
      </Drawer>
    );
  }
  if (detail === null) {
    return (
      <Drawer title="Loading the payment plan…" onClose={onClose}>
        <Loading label="Loading the payment plan…" lines={5} />
      </Drawer>
    );
  }

  const current = detail.current;
  const version = current?.version ?? null;
  const isDraft = version?.status === "draft";
  const code = currencyCodeOf(detail.currency_id);
  const sections = [
    { key: "schedule", label: "Schedule" },
    { key: "terms", label: "Terms" },
    { key: "history", label: "History" },
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
          <span className="chip">
            <span className="chip-label">Contract</span>
            <strong className="mono">
              {money(version?.contract_value_covered ?? null, code)}
            </strong>
          </span>
          {detail.active_version_id && detail.active_version_id !== version?.id ? (
            <Badge tone="success">A different version is active</Badge>
          ) : null}
        </>
      }
      tabs={sections}
      activeTab={section}
      onSelectTab={setSection}
      onClose={onClose}
    >
      {error ? <Notice tone="error">{error}</Notice> : null}
      {notice ? <Notice tone="success">{notice}</Notice> : null}

      {section === "schedule" && current && version ? (
        <>
          <section>
            <SectionHeader title="Where this version stands" />
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
              reconciliation={current.reconciliation}
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
                <div className="form-grid form-grid-3">
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
                      className="input input-short"
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
                  <FormActions>
                    <Button
                      variant="primary"
                      disabled={busy || !series.first_due_date}
                      onClick={() => void addSeries()}
                    >
                      Add these dates
                    </Button>
                  </FormActions>
                </div>
              </SubPanel>
            ) : null}

            {isDraft && canPrepare ? (
              <>
                <div className="form-inline">
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
                </div>
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
            ) : current.installments.length === 0 ? (
              <EmptyState title="No instalments" hint="This version has no schedule." />
            ) : (
              <ScheduleTable
                installments={current.installments}
                currencyId={detail.currency_id}
              />
            )}
          </section>

          <section>
            <SectionHeader title="What happens next" />
            <ButtonRow>
              {canPrepare && isDraft ? (
                <Button
                  variant="primary"
                  disabled={busy || !current.reconciliation.is_reconciled}
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
              {canApprove && version.status === "submitted" ? (
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
              {canApprove && version.status === "approved" ? (
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
              {canPrepare && version.status === "active" ? (
                <>
                  <Button
                    disabled={busy}
                    onClick={() =>
                      askThen(
                        {
                          title: "Revise this plan",
                          label: "Why are the terms changing?",
                          hint: "The standing schedule keeps governing until the revision is activated.",
                          confirmLabel: "Open a revision",
                        },
                        (reason) =>
                          paymentPlans.createVersion(projectId, planId, {
                            change_reason: reason,
                          }),
                        "Revision opened. The current schedule still governs the sale.",
                      )
                    }
                  >
                    Revise
                  </Button>
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
            {isDraft && !current.reconciliation.is_reconciled ? (
              <p className="footnote">
                A schedule can only be put forward once it covers the contract exactly.
              </p>
            ) : null}
          </section>

          {version.status === "active" ? (
            <ContingentSection
              projectId={projectId}
              planId={planId}
              installments={current.installments}
              canPrepare={canPrepare}
              canApprove={canApprove}
              busy={busy}
              onAsk={askThen}
            />
          ) : null}
        </>
      ) : null}

      {section === "schedule" && !current ? (
        <EmptyState title="No version" hint="This plan has no schedule yet." />
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
          <SectionHeader title="Versions" />
          <ul className="chip-list">
            {detail.versions.map((entry) => (
              <li key={entry.id} className="chip">
                <span className="chip-label">v{entry.version_number}</span>
                <Badge tone={versionTone(entry.status)}>{versionLabel(entry.status)}</Badge>
                <span className="chip-label">{businessDate(entry.effective_date)}</span>
              </li>
            ))}
          </ul>
          <p className="footnote">
            Nothing is overwritten. A superseded schedule stays readable exactly as it governed.
          </p>
        </section>
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
 * The instalments still waiting on something, and what can be done about them.
 *
 * A construction milestone is listed but has no action: PR-MVP-09 certifies
 * those, and offering a button that claimed to would be the system inventing a
 * certificate.
 */
function ContingentSection({
  projectId,
  planId,
  installments,
  canPrepare,
  canApprove,
  busy,
  onAsk,
}: {
  projectId: string;
  planId: string;
  installments: PlanInstallment[];
  canPrepare: boolean;
  canApprove: boolean;
  busy: boolean;
  onAsk: (
    prompt: Omit<Ask, "run">,
    action: (value: string) => Promise<unknown>,
    done: string,
  ) => void;
}) {
  const waiting = installments.filter((row) => row.trigger_status === "awaiting_trigger");
  if (waiting.length === 0) return null;

  return (
    <section>
      <SectionHeader
        title="Awaiting a trigger"
        description="These amounts are contracted but not yet due. A forecast date does not make one due."
      />
      <ul className="chip-list">
        {waiting.map((row) => (
          <li key={row.id} className="chip">
            <span className="chip-label">#{row.sequence}</span>
            <strong>{row.label}</strong>
            <span className="chip-label">{triggerLabel(row.trigger_type)}</span>
            {row.trigger_type === "manual_approved_event" && canPrepare ? (
              <Button
                small
                variant="quiet"
                disabled={busy}
                onClick={() =>
                  onAsk(
                    {
                      title: `Attest that ${row.label} occurred`,
                      label: "Reference for the evidence",
                      hint: "An Approver / CFO must sanction it before the amount falls due.",
                      confirmLabel: "Submit attestation",
                    },
                    (reference) =>
                      paymentPlans.submitManualTrigger(projectId, planId, row.id, {
                        event_date: new Date().toISOString().slice(0, 10),
                        evidence_reference: reference,
                        reason: `Attested for ${row.label}`,
                      }),
                    "Attestation submitted for approval.",
                  )
                }
              >
                Attest
              </Button>
            ) : null}
            {row.trigger_type === "construction_milestone" ? (
              <span className="chip-label">Awaiting certification</span>
            ) : null}
          </li>
        ))}
      </ul>
      <p className="footnote">
        A construction milestone becomes due when construction certifies it, which this system
        does not yet record. Handover and title transfer resolve from the sale itself — use
        Refresh triggers once the event has happened.
      </p>
      {canApprove ? (
        <p className="footnote">
          Attestations awaiting your decision appear on the instalment they belong to.
        </p>
      ) : null}
    </section>
  );
}
