"use client";

import { useCallback, useEffect, useState } from "react";

import {
  Badge,
  Button,
  ButtonRow,
  Drawer,
  EmptyState,
  Field,
  Form,
  FormActions,
  KeyValue,
  KeyValueGrid,
  Loading,
  Notice,
  PromptDialog,
  Stat,
  StatRow,
  SubPanel,
  TableScroll,
} from "@/components/ui";
import { ApiError, collections } from "@/lib/api";
import type {
  CollectionAction,
  CollectionDispute,
  CollectionRefund,
  CollectionRestructure,
  CollectionSaleSummary,
  CollectionWaiver,
  RestructurePreview,
} from "@/lib/api";
import { businessDate, isPositive, money, todayISO } from "@/lib/format";

import { ReceiptPanel } from "./ReceiptPanel";
import {
  ACTION_TYPES,
  WAIVER_TYPES,
  actionLabel,
  bucketLabel,
  bucketTone,
  clearanceLabel,
  clearanceTone,
  disputeLabel,
  disputeTone,
  installmentLabel,
  installmentTone,
  refundLabel,
  refundTone,
  restructureLabel,
  restructureTone,
  unitCollectionLabel,
  unitCollectionTone,
  waiverLabel,
  waiverTone,
  waiverTypeLabel,
} from "./labels";

const TABS = [
  { key: "position", label: "Position" },
  { key: "receipts", label: "Receipts" },
  { key: "actions", label: "Follow-up" },
  { key: "exceptions", label: "Disputes & waivers" },
  { key: "restructure", label: "Restructure" },
  { key: "refunds", label: "Refunds" },
];

/**
 * One buyer's collections account, opened over the register that led to it.
 *
 * The Position tab is the whole answer to "where does this stand?", and it
 * shows the four figures that must never be conflated: what is scheduled, what
 * has actually been confirmed as received, how much of that has been applied,
 * and what is still outstanding. Unapplied cash sits between the second and
 * third, because it is the difference between them and it is where money hides.
 *
 * Nothing on this screen is computed here. Days overdue, aging bands,
 * outstanding balances and whether the account may be cleared all arrive from
 * the API already decided.
 */
export function CollectionAccount({
  projectId,
  saleId,
  saleNumber,
  unitNumber,
  clientName,
  currencyCode,
  roles,
  onClose,
  onChanged,
}: {
  projectId: string;
  saleId: string;
  saleNumber: string;
  unitNumber: string;
  clientName: string;
  currencyCode: string | null;
  roles: Set<string>;
  onClose: () => void;
  onChanged: () => void;
}) {
  const [tab, setTab] = useState("position");
  const [summary, setSummary] = useState<CollectionSaleSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const canCollect = roles.has("collections");
  const canConfirm = roles.has("finance");
  const canDecideWaiver = roles.has("approver_cfo");

  const load = useCallback(async () => {
    try {
      setSummary(await collections.account(projectId, saleId));
      setError(null);
    } catch (caught) {
      setSummary(null);
      setError(caught instanceof ApiError ? caught.message : "Could not load the account.");
    }
  }, [projectId, saleId]);

  useEffect(() => {
    void (async () => {
      await load();
    })();
  }, [load]);

  const refresh = async () => {
    await load();
    onChanged();
  };

  const act = async (run: () => Promise<unknown>, done: string) => {
    setBusy(true);
    setError(null);
    try {
      await run();
      setNotice(done);
      await refresh();
    } catch (caught) {
      setNotice(null);
      setError(caught instanceof ApiError ? caught.message : "That did not work.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Drawer
      eyebrow={`Unit ${unitNumber}`}
      title={clientName}
      subtitle={saleNumber}
      meta={
        summary ? (
          <ButtonRow>
            <Badge tone={unitCollectionTone(summary.derived_collection_status)}>
              {unitCollectionLabel(summary.derived_collection_status)}
            </Badge>
            {summary.oldest_overdue_days > 0 ? (
              <Badge tone="danger">{summary.oldest_overdue_days} days overdue</Badge>
            ) : null}
            {summary.open_disputes > 0 ? (
              <Badge tone="danger">
                {summary.open_disputes} open dispute{summary.open_disputes === 1 ? "" : "s"}
              </Badge>
            ) : null}
            {isPositive(summary.unapplied_cash) ? (
              <Badge tone="warning">
                {money(summary.unapplied_cash, currencyCode)} unapplied
              </Badge>
            ) : null}
          </ButtonRow>
        ) : null
      }
      tabs={TABS}
      activeTab={tab}
      onSelectTab={setTab}
      onClose={onClose}
    >
      {error ? <Notice tone="error">{error}</Notice> : null}
      {notice ? <Notice tone="success">{notice}</Notice> : null}
      {summary === null ? (
        <Loading label="Loading the account" />
      ) : (
        <>
          {tab === "position" ? (
            <PositionTab
              projectId={projectId}
              saleId={saleId}
              summary={summary}
              currencyCode={currencyCode}
              canCollect={canCollect}
              busy={busy}
              onAct={act}
            />
          ) : null}

          {tab === "receipts" ? (
            <ReceiptPanel
              projectId={projectId}
              saleId={saleId}
              summary={summary}
              currencyCode={currencyCode}
              canRecord={canCollect}
              canConfirm={canConfirm}
              onChanged={() => void refresh()}
            />
          ) : null}

          {tab === "actions" ? (
            <ActionsTab
              projectId={projectId}
              saleId={saleId}
              summary={summary}
              currencyCode={currencyCode}
              canCollect={canCollect}
              busy={busy}
              onAct={act}
            />
          ) : null}

          {tab === "exceptions" ? (
            <ExceptionsTab
              projectId={projectId}
              saleId={saleId}
              summary={summary}
              canCollect={canCollect}
              canDecideWaiver={canDecideWaiver}
              busy={busy}
              onAct={act}
            />
          ) : null}

          {tab === "restructure" ? (
            <RestructureTab
              projectId={projectId}
              saleId={saleId}
              summary={summary}
              currencyCode={currencyCode}
              canCollect={canCollect}
              busy={busy}
              onAct={act}
            />
          ) : null}

          {tab === "refunds" ? (
            <RefundsTab
              projectId={projectId}
              saleId={saleId}
              summary={summary}
              currencyCode={currencyCode}
              canCollect={canCollect}
              canConfirm={canConfirm}
              busy={busy}
              onAct={act}
            />
          ) : null}
        </>
      )}
    </Drawer>
  );
}

type Act = (run: () => Promise<unknown>, done: string) => Promise<void>;

/* ------------------------------------------------------------------------- */

function PositionTab({
  projectId,
  saleId,
  summary,
  currencyCode,
  canCollect,
  busy,
  onAct,
}: {
  projectId: string;
  saleId: string;
  summary: CollectionSaleSummary;
  currencyCode: string | null;
  canCollect: boolean;
  busy: boolean;
  onAct: Act;
}) {
  const [clearing, setClearing] = useState(false);
  const eligible = summary.clearance_blockers.length === 0;

  return (
    <div className="stack">
      <StatRow>
        <Stat label="Scheduled" value={money(summary.scheduled_total, currencyCode)} />
        <Stat
          label="Confirmed receipts"
          value={money(summary.confirmed_receipts_total, currencyCode)}
          note="Cash Finance has accepted"
        />
        <Stat
          label="Applied"
          value={money(summary.allocated_total, currencyCode)}
          note="Assigned to instalments"
        />
        <Stat
          label="Outstanding"
          value={money(summary.outstanding_total, currencyCode)}
          note={`of which ${money(summary.overdue_total, currencyCode)} overdue`}
        />
      </StatRow>

      {isPositive(summary.unapplied_cash) ? (
        <Notice tone="warning">
          {money(summary.unapplied_cash, currencyCode)} of confirmed cash has not been applied to
          any instalment. It is the buyer&rsquo;s money and it is not reducing their balance until
          somebody decides what it settles.
        </Notice>
      ) : null}

      <SubPanel title="Instalments">
        <TableScroll label="Instalments and the cash against them" fixedFirst>
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
              <th scope="col">Age</th>
              <th scope="col">State</th>
            </tr>
          </thead>
          <tbody>
            {summary.installments.map((row) => (
              <tr key={row.installment_id}>
                <th scope="row">
                  {row.sequence}. {row.label}
                </th>
                <td>{businessDate(row.due_date)}</td>
                <td className="num mono">{money(row.scheduled, currencyCode)}</td>
                <td className="num mono">{money(row.paid, currencyCode)}</td>
                <td className="num mono">{money(row.outstanding, currencyCode)}</td>
                <td className="num mono">{row.overdue_days > 0 ? row.overdue_days : "—"}</td>
                <td>
                  <Badge tone={bucketTone(row.bucket)}>{bucketLabel(row.bucket)}</Badge>
                </td>
                <td>
                  <Badge tone={installmentTone(row.status)}>{installmentLabel(row.status)}</Badge>
                  {row.has_active_waiver ? (
                    <p className="hint">
                      Collection paused to {businessDate(row.waived_until)}. Balance still due.
                    </p>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </TableScroll>
      </SubPanel>

      <SubPanel
        title="Collection clearance"
        actions={
          canCollect && eligible ? (
            <Button variant="primary" onClick={() => setClearing(true)} disabled={busy}>
              Grant clearance
            </Button>
          ) : undefined
        }
      >
        <KeyValueGrid>
          <KeyValue
            label="Status"
            value={
              <Badge tone={clearanceTone(summary.collection_clearance_status)}>
                {clearanceLabel(summary.collection_clearance_status)}
              </Badge>
            }
          />
          <KeyValue label="Outstanding" value={money(summary.outstanding_total, currencyCode)} mono />
          <KeyValue label="Unapplied" value={money(summary.unapplied_cash, currencyCode)} mono />
          <KeyValue label="Open disputes" value={summary.open_disputes} mono />
        </KeyValueGrid>
        {eligible ? (
          <p className="hint">
            Nothing outstanding, nothing unapplied, nothing disputed. Collections may sign this
            account off for handover.
          </p>
        ) : (
          <Notice tone="warning">
            Collection clearance cannot be granted: {summary.clearance_blockers.join("; ")}.
          </Notice>
        )}
      </SubPanel>

      {clearing ? (
        <PromptDialog
          title="Grant collection clearance"
          hint="Record the reference of the evidence. This is Collections attesting that its own ledger is clear, checked against the figures above."
          label="Evidence reference"
          confirmLabel="Grant clearance"
          busy={busy}
          onCancel={() => setClearing(false)}
          onSubmit={(reference) => {
            setClearing(false);
            void onAct(
              () => collections.grantClearance(projectId, saleId, reference),
              "Collection clearance granted.",
            );
          }}
        />
      ) : null}
    </div>
  );
}

/* ------------------------------------------------------------------------- */

function ActionsTab({
  projectId,
  saleId,
  summary,
  currencyCode,
  canCollect,
  busy,
  onAct,
}: {
  projectId: string;
  saleId: string;
  summary: CollectionSaleSummary;
  currencyCode: string | null;
  canCollect: boolean;
  busy: boolean;
  onAct: Act;
}) {
  const [history, setHistory] = useState<CollectionAction[] | null>(null);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    action_type: "call",
    action_at: todayISO(),
    notes: "",
    promised_amount: "",
    promised_date: "",
    next_action_date: "",
  });

  const load = useCallback(async () => {
    try {
      setHistory(await collections.actions(projectId, saleId));
    } catch {
      setHistory([]);
    }
  }, [projectId, saleId]);

  useEffect(() => {
    void (async () => {
      await load();
    })();
  }, [load]);

  return (
    <div className="stack">
      <StatRow>
        <Stat
          label="Next follow-up"
          value={businessDate(summary.next_action_date)}
          note="Planned, not promised"
          small
        />
        <Stat
          label="Overdue"
          value={money(summary.overdue_total, currencyCode)}
          note={
            summary.oldest_overdue_days > 0
              ? `Oldest ${summary.oldest_overdue_days} days`
              : "Nothing past grace"
          }
          small
        />
      </StatRow>

      {canCollect ? (
        <SubPanel
          title="Record what you did"
          actions={
            <Button onClick={() => setOpen((value) => !value)}>
              {open ? "Cancel" : "Add an entry"}
            </Button>
          }
        >
          {open ? (
            <Form
              onSubmit={(event) => {
                event.preventDefault();
                void onAct(
                  () =>
                    collections.recordAction(projectId, saleId, {
                      action_type: form.action_type,
                      action_at: form.action_at,
                      notes: form.notes,
                      promised_amount: form.promised_amount || null,
                      promised_date: form.promised_date || null,
                      next_action_date: form.next_action_date || null,
                    }),
                  "Recorded.",
                ).then(() => {
                  setOpen(false);
                  setForm({
                    action_type: "call",
                    action_at: todayISO(),
                    notes: "",
                    promised_amount: "",
                    promised_date: "",
                    next_action_date: "",
                  });
                  void load();
                });
              }}
            >
              <Field label="What happened">
                <select
                  value={form.action_type}
                  onChange={(event) => setForm({ ...form, action_type: event.target.value })}
                >
                  {ACTION_TYPES.map((type) => (
                    <option key={type} value={type}>
                      {actionLabel(type)}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="When" hint="Something that has happened. Not a future date.">
                <input
                  type="date"
                  value={form.action_at}
                  max={todayISO()}
                  onChange={(event) => setForm({ ...form, action_at: event.target.value })}
                  required
                />
              </Field>
              <Field label="Notes">
                <textarea
                  value={form.notes}
                  rows={3}
                  onChange={(event) => setForm({ ...form, notes: event.target.value })}
                  required
                />
              </Field>
              {form.action_type === "promise_to_pay" ? (
                <>
                  <Field
                    label={`Amount promised${currencyCode ? ` (${currencyCode})` : ""}`}
                    hint="A promise is not a payment. It changes no balance."
                  >
                    <input
                      value={form.promised_amount}
                      inputMode="decimal"
                      onChange={(event) =>
                        setForm({ ...form, promised_amount: event.target.value })
                      }
                      required
                    />
                  </Field>
                  <Field label="Promised by">
                    <input
                      type="date"
                      value={form.promised_date}
                      onChange={(event) => setForm({ ...form, promised_date: event.target.value })}
                    />
                  </Field>
                </>
              ) : null}
              <Field label="Next follow-up" hint="May be in the future — it is a plan.">
                <input
                  type="date"
                  value={form.next_action_date}
                  onChange={(event) =>
                    setForm({ ...form, next_action_date: event.target.value })
                  }
                />
              </Field>
              <FormActions>
                <Button type="submit" variant="primary" disabled={busy}>
                  Record
                </Button>
              </FormActions>
            </Form>
          ) : (
            <p className="hint">
              Entries are appended and never edited. A mistake is followed by another note.
            </p>
          )}
        </SubPanel>
      ) : null}

      {history === null ? null : history.length === 0 ? (
        <EmptyState
          title="No follow-up recorded"
          hint="No collection follow-up has been recorded for this account."
        />
      ) : (
        <TableScroll label="Collection actions">
          <thead>
            <tr>
              <th scope="col">Date</th>
              <th scope="col">Action</th>
              <th scope="col">Notes</th>
              <th scope="col" className="num">
                Promised
              </th>
              <th scope="col">Next</th>
            </tr>
          </thead>
          <tbody>
            {history.map((row) => (
              <tr key={row.id}>
                <th scope="row">{businessDate(row.action_at)}</th>
                <td>{actionLabel(row.action_type)}</td>
                <td>{row.notes}</td>
                <td className="num mono">
                  {row.promised_amount ? money(row.promised_amount, currencyCode) : "—"}
                  {row.promised_date ? (
                    <p className="hint">by {businessDate(row.promised_date)}</p>
                  ) : null}
                </td>
                <td>{businessDate(row.next_action_date)}</td>
              </tr>
            ))}
          </tbody>
        </TableScroll>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------------- */

function ExceptionsTab({
  projectId,
  saleId,
  summary,
  canCollect,
  canDecideWaiver,
  busy,
  onAct,
}: {
  projectId: string;
  saleId: string;
  summary: CollectionSaleSummary;
  canCollect: boolean;
  canDecideWaiver: boolean;
  busy: boolean;
  onAct: Act;
}) {
  const [disputes, setDisputes] = useState<CollectionDispute[] | null>(null);
  const [waivers, setWaivers] = useState<CollectionWaiver[] | null>(null);
  const [openingDispute, setOpeningDispute] = useState<string | null>(null);
  const [closing, setClosing] = useState<{ id: string; withdraw: boolean } | null>(null);
  const [deciding, setDeciding] = useState<{ id: string; action: "reject" | "revoke" } | null>(
    null,
  );
  const [waiverFor, setWaiverFor] = useState<string | null>(null);
  const [waiverForm, setWaiverForm] = useState({
    waiver_type: "collection_hold",
    waived_until: "",
    reason: "",
  });

  const load = useCallback(async () => {
    const [d, w] = await Promise.all([
      collections.disputes(projectId, saleId).catch(() => []),
      collections.waivers(projectId, saleId).catch(() => []),
    ]);
    setDisputes(d);
    setWaivers(w);
  }, [projectId, saleId]);

  useEffect(() => {
    void (async () => {
      await load();
    })();
  }, [load]);

  const after = (run: () => Promise<unknown>, done: string) =>
    void onAct(run, done).then(() => void load());

  const rowFor = (installmentId: string) =>
    summary.installments.find((row) => row.installment_id === installmentId);

  return (
    <div className="stack">
      <Notice tone="info">
        Neither a dispute nor a waiver changes what is owed. A contested instalment keeps its
        balance and keeps ageing; an approved waiver pauses collection action and nothing else.
      </Notice>

      <SubPanel title="Disputes">
        {canCollect ? (
          <Field label="Contest an instalment">
            <select
              value={openingDispute ?? ""}
              onChange={(event) => setOpeningDispute(event.target.value || null)}
            >
              <option value="">Choose an instalment</option>
              {summary.installments
                .filter((row) => !row.is_disputed)
                .map((row) => (
                  <option key={row.installment_id} value={row.installment_id}>
                    {row.sequence}. {row.label}
                  </option>
                ))}
            </select>
          </Field>
        ) : null}

        {disputes === null ? null : disputes.length === 0 ? (
          <EmptyState title="No disputes" hint="No open collection disputes." />
        ) : (
          <TableScroll label="Disputes">
            <thead>
              <tr>
                <th scope="col">Instalment</th>
                <th scope="col">Reason</th>
                <th scope="col">State</th>
                <th scope="col">Outcome</th>
                <th scope="col">
                  <span className="visually-hidden">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {disputes.map((dispute) => {
                const row = rowFor(dispute.installment_id);
                return (
                  <tr key={dispute.id}>
                    <th scope="row">
                      {row ? `${row.sequence}. ${row.label}` : "Superseded instalment"}
                      {row && row.overdue_days > 0 ? (
                        <p className="hint">{row.overdue_days} days overdue, still owed</p>
                      ) : null}
                    </th>
                    <td>{dispute.reason}</td>
                    <td>
                      <Badge tone={disputeTone(dispute.status)}>
                        {disputeLabel(dispute.status)}
                      </Badge>
                    </td>
                    <td>{dispute.resolution ?? "—"}</td>
                    <td>
                      {canCollect && dispute.status === "open" ? (
                        <ButtonRow>
                          <Button
                            disabled={busy}
                            onClick={() => setClosing({ id: dispute.id, withdraw: false })}
                          >
                            Resolve
                          </Button>
                          <Button
                            disabled={busy}
                            onClick={() => setClosing({ id: dispute.id, withdraw: true })}
                          >
                            Withdraw
                          </Button>
                        </ButtonRow>
                      ) : null}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </TableScroll>
        )}
      </SubPanel>

      <SubPanel
        title="Waivers"
        actions={
          canCollect ? (
            <Button onClick={() => setWaiverFor((open) => (open === null ? "" : null))}>
              {waiverFor === null ? "Ask for a pause" : "Cancel"}
            </Button>
          ) : undefined
        }
      >
        {waiverFor !== null && canCollect ? (
          <Form
            onSubmit={(event) => {
              event.preventDefault();
              after(
                () =>
                  collections.submitWaiver(projectId, waiverFor, {
                    waiver_type: waiverForm.waiver_type,
                    waived_until: waiverForm.waived_until,
                    reason: waiverForm.reason,
                  }),
                "Waiver submitted for approval.",
              );
              setWaiverFor(null);
            }}
          >
            <Field label="Instalment">
              <select
                value={waiverFor}
                onChange={(event) => setWaiverFor(event.target.value)}
                required
              >
                <option value="">Choose an instalment</option>
                {summary.installments.map((row) => (
                  <option key={row.installment_id} value={row.installment_id}>
                    {row.sequence}. {row.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Type">
              <select
                value={waiverForm.waiver_type}
                onChange={(event) =>
                  setWaiverForm({ ...waiverForm, waiver_type: event.target.value })
                }
              >
                {WAIVER_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {waiverTypeLabel(type)}
                  </option>
                ))}
              </select>
            </Field>
            <Field
              label="Paused until"
              hint="A future date. The contractual balance remains due throughout."
            >
              <input
                type="date"
                value={waiverForm.waived_until}
                onChange={(event) =>
                  setWaiverForm({ ...waiverForm, waived_until: event.target.value })
                }
                required
              />
            </Field>
            <Field label="Reason">
              <textarea
                value={waiverForm.reason}
                rows={2}
                onChange={(event) => setWaiverForm({ ...waiverForm, reason: event.target.value })}
                required
              />
            </Field>
            <FormActions>
              <Button type="submit" variant="primary" disabled={busy}>
                Submit for approval
              </Button>
            </FormActions>
          </Form>
        ) : null}

        {waivers === null ? null : waivers.length === 0 ? (
          <EmptyState title="No waivers" hint="No collection waiver has been asked for." />
        ) : (
          <TableScroll label="Waivers">
            <thead>
              <tr>
                <th scope="col">Instalment</th>
                <th scope="col">Type</th>
                <th scope="col">Until</th>
                <th scope="col">Reason</th>
                <th scope="col">State</th>
                <th scope="col">
                  <span className="visually-hidden">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {waivers.map((waiver) => {
                const row = rowFor(waiver.installment_id);
                return (
                  <tr key={waiver.id}>
                    <th scope="row">
                      {row ? `${row.sequence}. ${row.label}` : "Superseded instalment"}
                    </th>
                    <td>{waiverTypeLabel(waiver.waiver_type)}</td>
                    <td>{businessDate(waiver.waived_until)}</td>
                    <td>{waiver.reason}</td>
                    <td>
                      <Badge tone={waiverTone(waiver.status)}>{waiverLabel(waiver.status)}</Badge>
                      {waiver.rejection_reason ? (
                        <p className="hint">{waiver.rejection_reason}</p>
                      ) : null}
                      {waiver.revocation_reason ? (
                        <p className="hint">{waiver.revocation_reason}</p>
                      ) : null}
                    </td>
                    <td>
                      {canDecideWaiver && waiver.status === "submitted" ? (
                        <ButtonRow>
                          <Button
                            disabled={busy}
                            onClick={() =>
                              after(
                                () => collections.approveWaiver(projectId, waiver.id),
                                "Waiver approved. The balance remains due.",
                              )
                            }
                          >
                            Approve
                          </Button>
                          <Button
                            disabled={busy}
                            onClick={() => setDeciding({ id: waiver.id, action: "reject" })}
                          >
                            Refuse
                          </Button>
                        </ButtonRow>
                      ) : null}
                      {canDecideWaiver && waiver.status === "approved" ? (
                        <Button
                          disabled={busy}
                          onClick={() => setDeciding({ id: waiver.id, action: "revoke" })}
                        >
                          Withdraw
                        </Button>
                      ) : null}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </TableScroll>
        )}
      </SubPanel>

      {openingDispute ? (
        <PromptDialog
          title="Contest this instalment"
          hint="The instalment stays due, keeps its balance and keeps ageing. This records that the buyer disputes it."
          label="What is disputed"
          confirmLabel="Open dispute"
          busy={busy}
          onCancel={() => setOpeningDispute(null)}
          onSubmit={(reason) => {
            const target = openingDispute;
            setOpeningDispute(null);
            after(
              () => collections.openDispute(projectId, target, reason),
              "Dispute opened. The balance is unchanged.",
            );
          }}
        />
      ) : null}

      {closing ? (
        <PromptDialog
          title={closing.withdraw ? "Withdraw this dispute" : "Resolve this dispute"}
          label="Outcome"
          confirmLabel={closing.withdraw ? "Withdraw" : "Resolve"}
          busy={busy}
          onCancel={() => setClosing(null)}
          onSubmit={(resolution) => {
            const target = closing;
            setClosing(null);
            after(
              () =>
                target.withdraw
                  ? collections.withdrawDispute(projectId, target.id, resolution)
                  : collections.resolveDispute(projectId, target.id, resolution),
              "Dispute closed.",
            );
          }}
        />
      ) : null}

      {deciding ? (
        <PromptDialog
          title={deciding.action === "reject" ? "Refuse this waiver" : "Withdraw this waiver"}
          label="Reason"
          confirmLabel={deciding.action === "reject" ? "Refuse" : "Withdraw"}
          busy={busy}
          onCancel={() => setDeciding(null)}
          onSubmit={(reason) => {
            const target = deciding;
            setDeciding(null);
            after(
              () =>
                target.action === "reject"
                  ? collections.rejectWaiver(projectId, target.id, reason)
                  : collections.revokeWaiver(projectId, target.id, reason),
              "Recorded.",
            );
          }}
        />
      ) : null}
    </div>
  );
}

/* ------------------------------------------------------------------------- */

function RestructureTab({
  projectId,
  saleId,
  summary,
  currencyCode,
  canCollect,
  busy,
  onAct,
}: {
  projectId: string;
  saleId: string;
  summary: CollectionSaleSummary;
  currencyCode: string | null;
  canCollect: boolean;
  busy: boolean;
  onAct: Act;
}) {
  const [history, setHistory] = useState<CollectionRestructure[] | null>(null);
  const [preview, setPreview] = useState<RestructurePreview | null>(null);
  const [raising, setRaising] = useState(false);
  const [abandoning, setAbandoning] = useState<string | null>(null);

  const load = useCallback(async () => {
    const rows = await collections.restructures(projectId, saleId).catch(() => []);
    setHistory(rows);
    const open = rows.find((row) => row.status === "open");
    setPreview(
      open ? await collections.previewRestructure(projectId, open.id).catch(() => null) : null,
    );
  }, [projectId, saleId]);

  useEffect(() => {
    void (async () => {
      await load();
    })();
  }, [load]);

  const after = (run: () => Promise<unknown>, done: string) =>
    void onAct(run, done).then(() => void load());

  const open = history?.find((row) => row.status === "open") ?? null;

  return (
    <div className="stack">
      <Notice tone="info">
        Replacing a schedule that already has cash against it moves every allocation onto the new
        instalments in the same transaction. If a single unit of cash cannot be placed, nothing
        happens at all.
      </Notice>

      <StatRow>
        <Stat
          label="Confirmed receipts"
          value={money(summary.confirmed_receipts_total, currencyCode)}
          small
        />
        <Stat
          label="To carry forward"
          value={money(summary.allocated_total, currencyCode)}
          note="Cash currently applied"
          small
        />
        <Stat
          label="Stays unapplied"
          value={money(summary.unapplied_cash, currencyCode)}
          note="A restructure never applies it"
          small
        />
      </StatRow>

      {open === null && canCollect ? (
        <SubPanel
          title="Raise a restructure"
          actions={
            <Button onClick={() => setRaising((value) => !value)}>
              {raising ? "Cancel" : "Restructure this schedule"}
            </Button>
          }
        >
          {raising ? (
            <p className="hint">
              This opens a revision of the payment plan, copied from the schedule currently
              governing the sale. Edit it in the Payment Plan Builder and have the CFO approve it
              there — one schedule editor, one approval — then come back here to apply it.
            </p>
          ) : (
            <p className="hint">
              The ordinary payment-plan activation refuses once cash has been confirmed. This is
              the way through.
            </p>
          )}
          {raising ? (
            <PromptDialog
              title="Raise a restructure"
              hint="Why is this schedule being replaced? It goes on the revision's change reason too."
              label="Reason"
              confirmLabel="Raise restructure"
              busy={busy}
              onCancel={() => setRaising(false)}
              onSubmit={(reason) => {
                setRaising(false);
                after(
                  () => collections.createRestructure(projectId, saleId, { reason }),
                  "Restructure raised. Edit the replacement schedule in the payment plan.",
                );
              }}
            />
          ) : null}
        </SubPanel>
      ) : null}

      {open && preview ? (
        <SubPanel
          title={`${open.restructure_number} — what applying would do`}
          actions={
            canCollect ? (
              <ButtonRow>
                <Button
                  variant="primary"
                  disabled={busy || !preview.ready_to_apply}
                  onClick={() =>
                    after(
                      () => collections.applyRestructure(projectId, open.id),
                      "Restructure applied. Every unit of cash was carried forward.",
                    )
                  }
                >
                  Apply restructure
                </Button>
                <Button disabled={busy} onClick={() => setAbandoning(open.id)}>
                  Abandon
                </Button>
              </ButtonRow>
            ) : undefined
          }
        >
          <StatRow>
            <Stat
              label="Cash to carry"
              value={money(preview.carried_total, currencyCode)}
              note={`${preview.superseding} allocation${
                preview.superseding === 1 ? "" : "s"
              } superseded`}
              small
            />
            <Stat
              label="Unapplied, unchanged"
              value={money(preview.unapplied_total, currencyCode)}
              small
            />
            <Stat
              label="Confirmed receipts, unchanged"
              value={money(preview.confirmed_receipts_total, currencyCode)}
              small
            />
          </StatRow>

          {preview.ready_to_apply ? (
            <Notice tone="success">
              Ready to apply. The three figures above will be identical afterwards.
            </Notice>
          ) : (
            <Notice tone="warning">
              Not ready: {preview.blockers.join("; ")}.
            </Notice>
          )}

          {preview.lines.length > 0 ? (
            <TableScroll label="Cash carried forward">
              <thead>
                <tr>
                  <th scope="col">Receipt</th>
                  <th scope="col">Lands on</th>
                  <th scope="col" className="num">
                    Amount
                  </th>
                </tr>
              </thead>
              <tbody>
                {preview.lines.map((line, index) => (
                  <tr key={`${line.receipt_id}-${line.installment_id}-${index}`}>
                    <th scope="row" className="mono">
                      {line.receipt_id.slice(0, 8)}
                    </th>
                    <td className="mono">{line.installment_id.slice(0, 8)}</td>
                    <td className="num mono">{money(line.amount, currencyCode)}</td>
                  </tr>
                ))}
              </tbody>
            </TableScroll>
          ) : null}
        </SubPanel>
      ) : null}

      {history === null ? null : history.length === 0 ? (
        <EmptyState title="No restructures" hint="This schedule has never been restructured." />
      ) : (
        <TableScroll label="Restructures">
          <thead>
            <tr>
              <th scope="col">Reference</th>
              <th scope="col">Reason</th>
              <th scope="col">State</th>
              <th scope="col">Applied</th>
            </tr>
          </thead>
          <tbody>
            {history.map((row) => (
              <tr key={row.id}>
                <th scope="row" className="mono">
                  {row.restructure_number}
                </th>
                <td>{row.reason}</td>
                <td>
                  <Badge tone={restructureTone(row.status)}>{restructureLabel(row.status)}</Badge>
                  {row.abandonment_reason ? (
                    <p className="hint">{row.abandonment_reason}</p>
                  ) : null}
                </td>
                <td>{row.applied_at ? businessDate(row.applied_at.slice(0, 10)) : "—"}</td>
              </tr>
            ))}
          </tbody>
        </TableScroll>
      )}

      {abandoning ? (
        <PromptDialog
          title="Abandon this restructure"
          hint="Nothing financial moves. The active schedule keeps governing and its allocations stay exactly where they are."
          label="Reason"
          confirmLabel="Abandon"
          busy={busy}
          onCancel={() => setAbandoning(null)}
          onSubmit={(reason) => {
            const target = abandoning;
            setAbandoning(null);
            after(
              () => collections.abandonRestructure(projectId, target, reason),
              "Restructure abandoned.",
            );
          }}
        />
      ) : null}
    </div>
  );
}

/* ------------------------------------------------------------------------- */

function RefundsTab({
  projectId,
  saleId,
  summary,
  currencyCode,
  canCollect,
  canConfirm,
  busy,
  onAct,
}: {
  projectId: string;
  saleId: string;
  summary: CollectionSaleSummary;
  currencyCode: string | null;
  canCollect: boolean;
  canConfirm: boolean;
  busy: boolean;
  onAct: Act;
}) {
  const [refunds, setRefunds] = useState<CollectionRefund[] | null>(null);
  const [reversing, setReversing] = useState<string | null>(null);

  const load = useCallback(async () => {
    setRefunds(await collections.refunds(projectId, saleId).catch(() => []));
  }, [projectId, saleId]);

  useEffect(() => {
    void (async () => {
      await load();
    })();
  }, [load]);

  const after = (run: () => Promise<unknown>, done: string) =>
    void onAct(run, done).then(() => void load());

  // Money that has already gone out stays on the file after the debt ends. A
  // withdrawn cancellation takes the amount due back to zero, and hiding the
  // panel on that alone would take a confirmed payment off the screen with it.
  const hasRefundHistory =
    isPositive(summary.refund_due_total) || isPositive(summary.refund_confirmed_total);

  if (!hasRefundHistory) {
    return (
      <EmptyState
        title="No refund due"
        hint="This contract has not been cancelled with an amount owed back to the buyer."
      />
    );
  }

  return (
    <div className="stack">
      <StatRow>
        <Stat
          label="Refund due"
          value={money(summary.refund_due_total, currencyCode)}
          note="Approved on the cancellation"
        />
        <Stat
          label="Actually refunded"
          value={money(summary.refund_confirmed_total, currencyCode)}
          note="Confirmed as having left"
        />
        <Stat
          label="Still to pay"
          value={money(summary.refund_outstanding, currencyCode)}
        />
      </StatRow>

      <Notice tone="info">
        What is owed and what has been paid are two figures and stay two. A refund is money
        leaving; it is never recorded as a negative receipt.
      </Notice>

      {refunds === null ? null : refunds.length === 0 ? (
        <EmptyState
          title="Nothing refunded yet"
          hint="No repayment has been recorded against this cancellation."
        />
      ) : (
        <TableScroll label="Refunds">
          <thead>
            <tr>
              <th scope="col">Reference</th>
              <th scope="col">Date</th>
              <th scope="col" className="num">
                Amount
              </th>
              <th scope="col">State</th>
              <th scope="col">
                <span className="visually-hidden">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {refunds.map((refund) => (
              <tr key={refund.id}>
                <th scope="row" className="mono">
                  {refund.refund_number}
                </th>
                <td>{businessDate(refund.refund_date)}</td>
                <td className="num mono">{money(refund.amount, currencyCode)}</td>
                <td>
                  <Badge tone={refundTone(refund.status)}>{refundLabel(refund.status)}</Badge>
                  {refund.reversal_reason ? (
                    <p className="hint">{refund.reversal_reason}</p>
                  ) : null}
                </td>
                <td>
                  <ButtonRow>
                    {canConfirm && refund.status === "recorded" ? (
                      <Button
                        disabled={busy}
                        onClick={() =>
                          after(
                            () => collections.confirmRefund(projectId, refund.id),
                            "Refund confirmed as paid.",
                          )
                        }
                      >
                        Confirm
                      </Button>
                    ) : null}
                    {canConfirm && refund.status === "confirmed" ? (
                      <Button disabled={busy} onClick={() => setReversing(refund.id)}>
                        Reverse
                      </Button>
                    ) : null}
                  </ButtonRow>
                </td>
              </tr>
            ))}
          </tbody>
        </TableScroll>
      )}

      {canCollect ? (
        <p className="hint">
          Record a repayment from the cancellation on the deal file, where the amount due and its
          approval live.
        </p>
      ) : null}

      {reversing ? (
        <PromptDialog
          title="Reverse this refund"
          hint="The row stays, reversed, and the amount goes back to still-to-pay."
          label="Reason"
          confirmLabel="Reverse"
          busy={busy}
          onCancel={() => setReversing(null)}
          onSubmit={(reason) => {
            const target = reversing;
            setReversing(null);
            after(
              () => collections.reverseRefund(projectId, target, reason),
              "Refund reversed.",
            );
          }}
        />
      ) : null}
    </div>
  );
}
