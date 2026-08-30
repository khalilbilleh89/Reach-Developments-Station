"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, sales } from "@/lib/api";
import type {
  ClientParty,
  HandoverDetail,
  LegalTimeline,
  ReservationDetail,
  SaleDetail,
  SalesClient,
} from "@/lib/api";
import { Badge, EmptyState, Field, Loading, Notice, Panel } from "@/components/ui";
import { statusLabel } from "@/components/projects/inventory/statusLabels";
import {
  ADJUSTMENT_TYPES,
  RATE_ADJUSTMENTS,
  adjustmentLabel,
  cancellationLabel,
  clearanceLabel,
  exceptionLabel,
  gateLabel,
  handoverLabel,
  kycLabel,
  legalEventLabel,
  reservationLabel,
  saleLabel,
  treatmentLabel,
} from "@/components/projects/sales/labels";

/**
 * One deal file: this buyer, this unit, this price, and how far it has got.
 *
 * Deliberately one screen rather than six. A reservation, an SPA, a legal
 * timeline, a cancellation and a handover are five records of one transaction,
 * and somebody answering "where is unit 101?" should not have to visit five
 * pages to find out.
 *
 * Nothing in this file calculates. Every figure shown was computed by the
 * server: the discount, the tax, the contract price, the effective net revenue
 * and whether an approval is required. The browser sends inputs and displays
 * what comes back, so there is never a second implementation of the waterfall
 * quietly disagreeing with the first.
 *
 * Personal data is likewise the server's decision. A party arrives with an
 * identity document number or without the field at all, and this file renders
 * what it was given rather than deciding who deserves to see what.
 */

const LEGAL_EVENT_TYPES = [
  "spa_drafted",
  "spa_approved",
  "spa_issued",
  "buyer_signed",
  "seller_signed",
  "stamped",
  "stamp_duty_recorded",
  "land_registry_lodged",
  "land_registry_accepted",
  "registered",
  "title_transfer_pending",
  "title_transferred",
  "withdrawal_started",
  "withdrawn",
];

/**
 * Which steps a cancellation case may be offered next.
 *
 * A courtesy, not the control: the server holds the same map and refuses
 * anything outside it, along with the gates — registry withdrawal recorded,
 * financial terms approved — that this table says nothing about. Offering a
 * button the server would refuse is a worse screen than offering none.
 */
const CANCELLATION_NEXT: Record<string, string[]> = {
  notice: ["cure", "termination_pending_approval", "withdrawn"],
  cure: ["termination_pending_approval", "withdrawn"],
  termination_pending_approval: [
    "withdrawal_pending",
    "ready_for_unit_return",
    "withdrawn",
  ],
  withdrawal_pending: ["ready_for_unit_return"],
  ready_for_unit_return: ["withdrawn"],
};

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function Money({ label, value }: { label: string; value: string | null }) {
  return (
    <div>
      <dt className="reference-term">{label}</dt>
      <dd className="reference-value mono nowrap">{value ?? "—"}</dd>
    </div>
  );
}

function Line({ label, value }: { label: string; value: string | null }) {
  return (
    <div>
      <dt className="reference-term">{label}</dt>
      <dd className="reference-value">{value ?? "—"}</dd>
    </div>
  );
}

function PartyList({ parties }: { parties: ClientParty[] }) {
  if (parties.length === 0) {
    return <EmptyState title="No buyers recorded yet" hint="A unit cannot be committed until the buyer shares total 1.000000." />;
  }
  return (
    <div className="table-scroll">
      <table className="table">
        <caption className="visually-hidden">Buyer parties</caption>
        <thead>
          <tr>
            <th scope="col">Name as identification</th>
            <th scope="col">Role</th>
            <th scope="col">Share</th>
            <th scope="col">Nationality</th>
            {"identity_document_number" in (parties[0] ?? {}) ? (
              <th scope="col">Identity document</th>
            ) : null}
          </tr>
        </thead>
        <tbody>
          {parties.map((party) => (
            <tr key={party.id}>
              <th scope="row">{party.name_as_identification}</th>
              <td>{party.party_role === "purchaser" ? "Purchaser" : "Joint purchaser"}</td>
              <td className="mono nowrap">{party.share_fraction}</td>
              <td>{party.nationality_code ?? "—"}</td>
              {"identity_document_number" in party ? (
                <td className="mono">
                  {party.identity_document_type ?? "—"} {party.identity_document_number ?? ""}
                </td>
              ) : null}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function LegalTimelineView({
  timeline,
  canRecord,
  busy,
  onReverse,
}: {
  timeline: LegalTimeline;
  canRecord: boolean;
  busy: boolean;
  onReverse: (eventId: string, reason: string) => Promise<void>;
}) {
  const effective = new Set(timeline.effective_event_ids);
  if (timeline.events.length === 0) {
    return <EmptyState title="Nothing recorded yet" hint="Legal records each milestone as it happens." />;
  }
  return (
    <div className="table-scroll">
      <table className="table">
        <caption className="visually-hidden">Legal timeline</caption>
        <thead>
          <tr>
            <th scope="col">Milestone</th>
            <th scope="col">Date</th>
            <th scope="col">Authority reference</th>
            <th scope="col">Document</th>
            <th scope="col">Fee</th>
            <th scope="col">Standing</th>
            {canRecord ? <th scope="col">Correction</th> : null}
          </tr>
        </thead>
        <tbody>
          {timeline.events.map((event) => (
            <tr key={event.id}>
              <th scope="row">
                {legalEventLabel(event.event_type)}
                {event.reverses_event_id ? " — withdrawn" : ""}
              </th>
              <td className="nowrap">{event.event_date}</td>
              <td>{event.authority_reference ?? "—"}</td>
              <td>{event.document_reference ?? "—"}</td>
              <td className="mono nowrap">{event.fee_amount ?? "—"}</td>
              <td>
                {event.reverses_event_id ? (
                  <Badge tone="muted">Correction</Badge>
                ) : effective.has(event.id) ? (
                  <Badge tone="success">Stands</Badge>
                ) : (
                  <Badge tone="muted">Withdrawn</Badge>
                )}
              </td>
              {canRecord ? (
                <td>
                  {event.reverses_event_id === null && effective.has(event.id) ? (
                    <button
                      className="button button-small"
                      type="button"
                      disabled={busy}
                      onClick={() => {
                        const reason = window.prompt("Why is this event being withdrawn?");
                        if (reason) void onReverse(event.id, reason);
                      }}
                    >
                      Withdraw
                    </button>
                  ) : null}
                </td>
              ) : null}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function HandoverView({
  detail,
  clearanceRoles,
  busy,
  onGrant,
  onRevoke,
  onComplete,
  canRunHandover,
}: {
  detail: HandoverDetail;
  clearanceRoles: Set<string>;
  busy: boolean;
  onGrant: (type: string, reference: string) => Promise<void>;
  onRevoke: (type: string, reason: string) => Promise<void>;
  onComplete: (body: Record<string, unknown>) => Promise<void>;
  canRunHandover: boolean;
}) {
  const [form, setForm] = useState({
    handover_date: detail.handover.handover_date ?? today(),
    acceptance_document_reference: detail.handover.acceptance_document_reference ?? "",
    keys_reference: detail.handover.keys_reference ?? "",
  });
  const current = new Map<string, (typeof detail.clearances)[number]>();
  for (const clearance of detail.clearances) {
    if (clearance.status !== "revoked") current.set(clearance.clearance_type, clearance);
  }
  // Two of the server's blockers are about the very fields this form supplies,
  // so they must not disable the button that would supply them. Everything else
  // is somebody else's sign-off and genuinely blocks. The server checks all of
  // them again either way — this only decides whether the button is worth
  // offering.
  const supplied = ["Handover date not recorded", "Acceptance document reference not recorded"];
  const outstanding = detail.blockers.filter((blocker) => !supplied.includes(blocker));
  const ready =
    outstanding.length === 0 &&
    form.handover_date !== "" &&
    form.acceptance_document_reference !== "";

  return (
    <>
      <dl className="reference-list">
        <Line label="Status" value={handoverLabel(detail.handover.status)} />
        <Line label="Readiness" value={detail.handover.readiness_date} />
        <Line label="Inspection" value={detail.handover.inspection_date} />
        <Line label="Snagging" value={detail.handover.snag_status} />
        <Line label="Client notice" value={detail.handover.client_notice_date} />
        <Line label="Scheduled" value={detail.handover.scheduled_handover_date} />
        <Line label="Handed over" value={detail.handover.handover_date} />
        <Line label="Acceptance document" value={detail.handover.acceptance_document_reference} />
      </dl>

      <h3 className="section-heading">Clearances</h3>
      <div className="table-scroll">
        <table className="table">
          <caption className="visually-hidden">Handover clearances</caption>
          <thead>
            <tr>
              <th scope="col">Department</th>
              <th scope="col">Status</th>
              <th scope="col">Evidence</th>
              <th scope="col">Action</th>
            </tr>
          </thead>
          <tbody>
            {["legal", "collection", "delivery"].map((type) => {
              const clearance = current.get(type);
              const mine = clearanceRoles.has(type);
              return (
                <tr key={type}>
                  <th scope="row">{clearanceLabel(type)}</th>
                  <td>
                    {clearance?.status === "cleared" ? (
                      <Badge tone="success">Given</Badge>
                    ) : (
                      <Badge tone="muted">Pending</Badge>
                    )}
                  </td>
                  <td>{clearance?.evidence_reference ?? "—"}</td>
                  <td>
                    {!mine ? (
                      <span className="subtle">Another team&rsquo;s to give</span>
                    ) : clearance?.status === "cleared" ? (
                      <button
                        className="button button-small"
                        type="button"
                        disabled={busy}
                        onClick={() => {
                          const reason = window.prompt("Why is this clearance being withdrawn?");
                          if (reason) void onRevoke(type, reason);
                        }}
                      >
                        Withdraw
                      </button>
                    ) : (
                      <button
                        className="button button-small"
                        type="button"
                        disabled={busy}
                        onClick={() => {
                          const reference = window.prompt("Reference for the evidence:");
                          if (reference) void onGrant(type, reference);
                        }}
                      >
                        Give clearance
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {detail.blockers.length > 0 ? (
        <Notice tone="info">Still outstanding: {detail.blockers.join("; ")}.</Notice>
      ) : null}

      {canRunHandover && detail.handover.status !== "handed_over" ? (
        <form
          className="form-grid"
          onSubmit={(event) => {
            event.preventDefault();
            void onComplete({
              handover_date: form.handover_date,
              ...(form.acceptance_document_reference
                ? { acceptance_document_reference: form.acceptance_document_reference }
                : {}),
              ...(form.keys_reference ? { keys_reference: form.keys_reference } : {}),
            });
          }}
        >
          <Field label="Handover date">
            <input
              className="input"
              type="date"
              value={form.handover_date}
              onChange={(event) => setForm({ ...form, handover_date: event.target.value })}
            />
          </Field>
          <Field label="Acceptance document reference">
            <input
              className="input"
              value={form.acceptance_document_reference}
              onChange={(event) =>
                setForm({ ...form, acceptance_document_reference: event.target.value })
              }
            />
          </Field>
          <Field label="Keys reference">
            <input
              className="input"
              value={form.keys_reference}
              onChange={(event) => setForm({ ...form, keys_reference: event.target.value })}
            />
          </Field>
          <div className="form-actions">
            <button className="button button-primary" type="submit" disabled={busy || !ready}>
              Complete handover
            </button>
          </div>
        </form>
      ) : null}
    </>
  );
}

export function DealFile({
  projectId,
  reservationId,
  saleId,
  roles,
  onClose,
  onChanged,
}: {
  projectId: string;
  reservationId: string | null;
  saleId: string | null;
  roles: Set<string>;
  onClose: () => void;
  onChanged: () => Promise<void>;
}) {
  const [reservation, setReservation] = useState<ReservationDetail | null>(null);
  const [sale, setSale] = useState<SaleDetail | null>(null);
  const [client, setClient] = useState<SalesClient | null>(null);
  const [parties, setParties] = useState<ClientParty[]>([]);
  const [shares, setShares] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [adjustment, setAdjustment] = useState({
    adjustment_type: ADJUSTMENT_TYPES[0],
    value: "",
    reason: "",
  });
  const [legalForm, setLegalForm] = useState({
    event_type: LEGAL_EVENT_TYPES[0],
    event_date: today(),
    authority_reference: "",
    document_reference: "",
  });
  const [cancelling, setCancelling] = useState(false);
  const [cancelForm, setCancelForm] = useState({
    initiated_by_party: "buyer",
    reason: "",
    notice_date: "",
    cure_deadline: "",
    forfeiture_amount: "",
    refund_due_amount: "",
  });

  const canPrepare = roles.has("sales_operations") || roles.has("sales_advisor");
  const canWriteSale = roles.has("sales_operations");
  const canApprove = roles.has("approver_cfo");
  const canRecordLegal = roles.has("legal");
  const canCancel = roles.has("sales_operations") || roles.has("legal");
  const clearanceRoles = new Set<string>();
  if (roles.has("legal")) clearanceRoles.add("legal");
  if (roles.has("collections")) clearanceRoles.add("collection");
  if (roles.has("project_manager") || roles.has("design_engineering")) {
    clearanceRoles.add("delivery");
  }

  const load = useCallback(async () => {
    try {
      let loadedSale = saleId ? await sales.contract(projectId, saleId) : null;
      const loadedReservation = reservationId
        ? await sales.reservation(projectId, reservationId)
        : loadedSale
          ? await sales.reservation(projectId, loadedSale.sale.reservation_id)
          : null;
      if (loadedSale === null && loadedReservation !== null) {
        // A contract drawn up while this panel was open. The deal file was
        // opened on the reservation and has to follow the deal, not the
        // identifier it happened to start from.
        const onUnit = await sales.contracts(projectId, {
          unit_id: loadedReservation.reservation.unit_id,
        });
        const live = onUnit.find((entry) => entry.status !== "cancelled");
        if (live) loadedSale = await sales.contract(projectId, live.id);
      }
      const clientId =
        loadedSale?.sale.client_id ?? loadedReservation?.reservation.client_id ?? null;
      setSale(loadedSale);
      setReservation(loadedReservation);
      if (clientId) {
        setClient(await sales.client(projectId, clientId));
        setParties(await sales.parties(projectId, clientId));
        const reconciliation = await sales.shareReconciliation(projectId, clientId);
        setShares(reconciliation.total_share_fraction);
      }
      setError(null);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not load the deal.");
    }
  }, [projectId, reservationId, saleId]);

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

  if (error && reservation === null && sale === null) {
    return (
      <Panel title="Deal">
        <Notice tone="error">{error}</Notice>
        <button className="button" type="button" onClick={onClose}>
          Close
        </button>
      </Panel>
    );
  }

  if (reservation === null && sale === null) {
    return <Loading label="Loading the deal…" />;
  }

  const terms = reservation?.reservation ?? null;
  const preparing = terms !== null && ["draft", "deposit_pending"].includes(terms.status);
  const isRate = RATE_ADJUSTMENTS.has(adjustment.adjustment_type);

  return (
    <Panel
      title={
        sale
          ? `${sale.sale.sale_number}${sale.sale.spa_number ? ` · ${sale.sale.spa_number}` : ""}`
          : (terms?.reservation_number ?? "Deal")
      }
      description="One buyer, one unit, one price, and how far it has got."
      actions={
        <button className="button button-small" type="button" onClick={onClose}>
          Close
        </button>
      }
    >
      {error ? <Notice tone="error">{error}</Notice> : null}
      {notice ? <Notice tone="success">{notice}</Notice> : null}

      <h3 className="section-heading">Buyer</h3>
      {client ? (
        <>
          <dl className="reference-list">
            <Line label="Client" value={`${client.client_number} · ${client.display_name}`} />
            <Line label="Identity checks" value={kycLabel(client.kyc_status)} />
            {"email" in client ? <Line label="Email" value={client.email ?? null} /> : null}
            {"phone" in client ? <Line label="Phone" value={client.phone ?? null} /> : null}
            {"address" in client ? <Line label="Address" value={client.address ?? null} /> : null}
            <Line
              label="Buyer shares"
              value={shares === null ? null : `${shares}${shares === "1.000000" ? "" : " — not yet a whole unit"}`}
            />
          </dl>
          <PartyList parties={parties} />
        </>
      ) : (
        <EmptyState title="Buyer not visible" hint="You may see this deal but not the buyer behind it." />
      )}

      {terms ? (
        <>
          <h3 className="section-heading">Reservation</h3>
          <div className="chip-list">
            <Badge tone={terms.status === "active" || terms.status === "extended" ? "success" : "neutral"}>
              {reservationLabel(terms.status)}
            </Badge>
            {reservation?.closure_required ? (
              <Badge tone="muted">Expired — closure required</Badge>
            ) : null}
            <span className="chip">Deposit: {gateLabel(terms.deposit_gate_status)}</span>
            <span className="chip">Approval: {exceptionLabel(terms.exception_approval_status)}</span>
          </div>
          <dl className="reference-list">
            <Line label="Number" value={terms.reservation_number} />
            <Line label="Reserved on" value={terms.reservation_date} />
            <Line label="Expires" value={terms.expires_on} />
            <Line label="Price locked until" value={terms.price_locked_until} />
            <Line label="Channel" value={terms.sales_channel_code} />
            <Line label="Branch" value={terms.sales_branch_code} />
            <Money label="Deposit required" value={terms.deposit_required_amount} />
            <Line label="Deposit evidence" value={terms.deposit_confirmation_reference} />
          </dl>

          <h3 className="section-heading">Quote</h3>
          <dl className="reference-list">
            <Money label="Approved list price" value={terms.reference_price_ex_tax} />
            <Money label="Paid upgrades" value={terms.paid_upgrade_amount} />
            <Money label="Payment plan adjustment" value={terms.payment_plan_adjustment_amount} />
            <Money label="Gross quoted" value={terms.gross_quoted_price_ex_tax} />
            <Money label="Cash discount" value={terms.cash_discount_amount} />
            <Money label="Seller credit" value={terms.seller_credit_amount} />
            <Money label="Net contract price" value={terms.net_contract_price_ex_tax} />
            <Money label="Seller costs" value={terms.seller_cost_total} />
            <Money label="Effective net revenue" value={terms.effective_net_revenue_preview} />
            <Money label="Tax" value={terms.tax_total} />
            <Money label="Buyer fees" value={terms.buyer_fee_total} />
            <Money label="Total buyer payable" value={terms.total_buyer_payable} />
          </dl>
          <p className="footnote">
            Seller costs sit beside the contract price and never inside it: a package the seller
            absorbs does not reduce what the buyer contracts to pay.
          </p>

          {terms.exception_approval_required ? (
            <Notice tone="info">
              {terms.exception_reason ?? "This quote needs sanctioning."}{" "}
              {terms.exception_required_role
                ? `Only ${terms.exception_required_role.replace("_", " ")} may approve it.`
                : ""}
            </Notice>
          ) : null}

          <h3 className="section-heading">Commercial inputs</h3>
          {reservation && reservation.adjustments.length > 0 ? (
            <div className="table-scroll">
              <table className="table">
                <caption className="visually-hidden">Commercial inputs</caption>
                <thead>
                  <tr>
                    <th scope="col">Input</th>
                    <th scope="col">Effect</th>
                    <th scope="col">Rate</th>
                    <th scope="col">Amount</th>
                    <th scope="col">Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {reservation.adjustments.map((item) => (
                    <tr key={item.id}>
                      <th scope="row">{adjustmentLabel(item.adjustment_type)}</th>
                      <td>{treatmentLabel(item.treatment)}</td>
                      <td className="mono nowrap">{item.rate_fraction ?? "—"}</td>
                      <td className="mono nowrap">{item.amount ?? "—"}</td>
                      <td>{item.reason ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState title="No adjustments" hint="The quote is the approved list price." />
          )}

          {canPrepare && preparing ? (
            <form
              className="form-grid"
              onSubmit={(event) => {
                event.preventDefault();
                void run(
                  () =>
                    sales.addAdjustment(projectId, terms.id, {
                      adjustment_type: adjustment.adjustment_type,
                      ...(isRate
                        ? { rate_fraction: adjustment.value }
                        : { amount: adjustment.value }),
                      ...(adjustment.reason ? { reason: adjustment.reason } : {}),
                    }),
                  "Recorded, and the quote re-run.",
                );
              }}
            >
              <Field label="Commercial input">
                <select
                  className="input"
                  value={adjustment.adjustment_type}
                  onChange={(event) =>
                    setAdjustment({ ...adjustment, adjustment_type: event.target.value })
                  }
                >
                  {ADJUSTMENT_TYPES.map((type) => (
                    <option key={type} value={type}>
                      {adjustmentLabel(type)}
                    </option>
                  ))}
                </select>
              </Field>
              <Field
                label={isRate ? "Rate (fraction)" : "Amount"}
                hint={isRate ? "0.050000 means five per cent." : undefined}
              >
                <input
                  className="input"
                  value={adjustment.value}
                  onChange={(event) => setAdjustment({ ...adjustment, value: event.target.value })}
                />
              </Field>
              <Field label="Reason">
                <input
                  className="input"
                  value={adjustment.reason}
                  onChange={(event) => setAdjustment({ ...adjustment, reason: event.target.value })}
                />
              </Field>
              <div className="form-actions">
                <button className="button" type="submit" disabled={busy}>
                  Record and re-quote
                </button>
              </div>
            </form>
          ) : null}

          <div className="chip-list">
            {canPrepare && preparing && terms.exception_approval_status === "pending" ? (
              <button
                className="button button-small"
                type="button"
                disabled={busy}
                onClick={() => {
                  const reason = window.prompt("Why is this exception justified?");
                  if (reason) {
                    void run(
                      () => sales.submitException(projectId, terms.id, reason),
                      "Put forward for sanction.",
                    );
                  }
                }}
              >
                Submit for approval
              </button>
            ) : null}
            {canApprove && terms.exception_approval_status === "submitted" ? (
              <>
                <button
                  className="button button-small"
                  type="button"
                  disabled={busy}
                  onClick={() => {
                    const reason = window.prompt("Why is this approved?");
                    if (reason) {
                      void run(
                        () => sales.decideException(projectId, terms.id, true, reason),
                        "Approved.",
                      );
                    }
                  }}
                >
                  Approve exception
                </button>
                <button
                  className="button button-small"
                  type="button"
                  disabled={busy}
                  onClick={() => {
                    const reason = window.prompt("Why is this refused?");
                    if (reason) {
                      void run(
                        () => sales.decideException(projectId, terms.id, false, reason),
                        "Refused.",
                      );
                    }
                  }}
                >
                  Refuse exception
                </button>
              </>
            ) : null}
            {canWriteSale && preparing && terms.deposit_gate_status === "pending" ? (
              <button
                className="button button-small"
                type="button"
                disabled={busy}
                onClick={() => {
                  const reference = window.prompt("Reference for the deposit evidence:");
                  if (reference) {
                    void run(
                      () => sales.confirmDeposit(projectId, terms.id, reference),
                      "Deposit evidence recorded. This is not a receipt.",
                    );
                  }
                }}
              >
                Record deposit evidence
              </button>
            ) : null}
            {canApprove && terms.deposit_gate_status === "pending" ? (
              <button
                className="button button-small"
                type="button"
                disabled={busy}
                onClick={() => {
                  const reason = window.prompt("Why is the deposit being waived?");
                  if (reason) {
                    void run(
                      () => sales.waiveDeposit(projectId, terms.id, reason),
                      "Deposit waived.",
                    );
                  }
                }}
              >
                Waive deposit
              </button>
            ) : null}
            {canPrepare && preparing ? (
              <button
                className="button button-small button-primary"
                type="button"
                disabled={busy}
                onClick={() =>
                  void run(
                    () => sales.activateReservation(projectId, terms.id),
                    "The unit is reserved for this buyer.",
                  )
                }
              >
                Activate reservation
              </button>
            ) : null}
            {canPrepare && ["active", "extended"].includes(terms.status) ? (
              <button
                className="button button-small"
                type="button"
                disabled={busy}
                onClick={() => {
                  const reason = window.prompt("Why is the reservation being cancelled?");
                  if (reason) {
                    void run(
                      () => sales.cancelReservation(projectId, terms.id, reason),
                      "Reservation cancelled.",
                    );
                  }
                }}
              >
                Cancel reservation
              </button>
            ) : null}
            {canPrepare && reservation?.closure_required ? (
              <button
                className="button button-small"
                type="button"
                disabled={busy}
                onClick={() =>
                  void run(
                    () => sales.expireReservation(projectId, terms.id),
                    "Reservation closed as expired.",
                  )
                }
              >
                Close as expired
              </button>
            ) : null}
            {canWriteSale && ["active", "extended"].includes(terms.status) && sale === null ? (
              <button
                className="button button-small button-primary"
                type="button"
                disabled={busy}
                onClick={() =>
                  void run(
                    () => sales.createContract(projectId, { reservation_id: terms.id }),
                    "Contract drafted at the reservation's frozen price.",
                  )
                }
              >
                Draw up contract
              </button>
            ) : null}
          </div>
        </>
      ) : null}

      {sale ? (
        <>
          <h3 className="section-heading">Sale contract</h3>
          <div className="chip-list">
            <Badge tone={sale.sale.status === "active" ? "success" : "neutral"}>
              {saleLabel(sale.sale.status)}
            </Badge>
            <span className="chip">First payment: {gateLabel(sale.sale.first_payment_gate_status)}</span>
            <span className="chip">Legal: {statusLabel(sale.legal.legal_status)}</span>
          </div>
          <dl className="reference-list">
            <Line label="Sale number" value={sale.sale.sale_number} />
            <Line label="SPA number" value={sale.sale.spa_number} />
            <Line label="Contract date" value={sale.sale.contract_date} />
            <Money label="Net contract price" value={sale.sale.net_contract_price_ex_tax} />
            <Money label="Seller costs" value={sale.sale.seller_cost_total} />
            <Money label="Effective net revenue" value={sale.sale.effective_net_revenue_snapshot} />
            <Money label="Tax" value={sale.sale.tax_total} />
            <Money label="Total contract price" value={sale.sale.total_contract_price} />
          </dl>
          <p className="footnote">
            Frozen at submission. Changing these terms means cancelling the pending contract,
            re-quoting the reservation and obtaining the approvals again.
          </p>

          <h3 className="section-heading">Contract parties</h3>
          <PartyList parties={sale.parties as unknown as ClientParty[]} />

          {sale.tax_lines.length > 0 ? (
            <>
              <h3 className="section-heading">Frozen taxes</h3>
              <div className="table-scroll">
                <table className="table">
                  <caption className="visually-hidden">Frozen tax lines</caption>
                  <thead>
                    <tr>
                      <th scope="col">Tax</th>
                      <th scope="col">Rate</th>
                      <th scope="col">Basis</th>
                      <th scope="col">Taxable</th>
                      <th scope="col">Amount</th>
                      <th scope="col">Valid on</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sale.tax_lines.map((line) => (
                      <tr key={line.id}>
                        <th scope="row">{line.label}</th>
                        <td className="mono nowrap">{line.rate_fraction}</td>
                        <td>{line.calculation_basis}</td>
                        <td className="mono nowrap">{line.taxable_amount}</td>
                        <td className="mono nowrap">{line.tax_amount}</td>
                        <td className="nowrap">{line.valid_on}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : null}

          <div className="chip-list">
            {canWriteSale && sale.sale.status === "draft" ? (
              <button
                className="button button-small button-primary"
                type="button"
                disabled={busy}
                onClick={() =>
                  void run(
                    () => sales.submitContract(projectId, sale.sale.id),
                    "Submitted for signature. The unit is now contract pending.",
                  )
                }
              >
                Submit for signature
              </button>
            ) : null}
            {canWriteSale && sale.sale.first_payment_gate_status === "pending" ? (
              <button
                className="button button-small"
                type="button"
                disabled={busy}
                onClick={() => {
                  const reference = window.prompt("Reference for the payment evidence:");
                  if (reference) {
                    void run(
                      () => sales.confirmFirstPayment(projectId, sale.sale.id, reference),
                      "First-payment evidence recorded. This is not a receipt.",
                    );
                  }
                }}
              >
                Record first-payment evidence
              </button>
            ) : null}
            {canApprove && sale.sale.first_payment_gate_status === "pending" ? (
              <button
                className="button button-small"
                type="button"
                disabled={busy}
                onClick={() => {
                  const reason = window.prompt("Why is the first payment being waived?");
                  if (reason) {
                    void run(
                      () => sales.waiveFirstPayment(projectId, sale.sale.id, reason),
                      "First payment waived.",
                    );
                  }
                }}
              >
                Waive first payment
              </button>
            ) : null}
            {canWriteSale && sale.sale.status === "signature_pending" ? (
              <button
                className="button button-small button-primary"
                type="button"
                disabled={busy}
                onClick={() =>
                  void run(
                    () => sales.activateContract(projectId, sale.sale.id),
                    "The contract is live and the unit is contracted.",
                  )
                }
              >
                Activate contract
              </button>
            ) : null}
            {canWriteSale && sale.sale.status === "active" && sale.handover === null ? (
              <button
                className="button button-small"
                type="button"
                disabled={busy}
                onClick={() =>
                  void run(
                    () => sales.createHandover(projectId, sale.sale.id),
                    "Handover opened with three clearances outstanding.",
                  )
                }
              >
                Open handover
              </button>
            ) : null}
            {canCancel &&
            sale.cancellation === null &&
            ["signature_pending", "active"].includes(sale.sale.status) ? (
              <button
                className="button button-small"
                type="button"
                disabled={busy}
                onClick={() => setCancelling(true)}
              >
                Start cancellation
              </button>
            ) : null}
          </div>

          {cancelling ? (
            <form
              className="form-grid"
              onSubmit={(event) => {
                event.preventDefault();
                void run(
                  () =>
                    sales.startCancellation(projectId, sale.sale.id, {
                      initiated_by_party: cancelForm.initiated_by_party,
                      reason: cancelForm.reason,
                      ...(cancelForm.notice_date ? { notice_date: cancelForm.notice_date } : {}),
                      ...(cancelForm.cure_deadline
                        ? { cure_deadline: cancelForm.cure_deadline }
                        : {}),
                      ...(cancelForm.forfeiture_amount
                        ? { forfeiture_amount: cancelForm.forfeiture_amount }
                        : {}),
                      ...(cancelForm.refund_due_amount
                        ? { refund_due_amount: cancelForm.refund_due_amount }
                        : {}),
                    }),
                  "Cancellation opened. The unit stays committed until it completes.",
                ).then(() => setCancelling(false))
              }}
            >
              <Field label="Initiated by">
                <select
                  className="input"
                  value={cancelForm.initiated_by_party}
                  onChange={(event) =>
                    setCancelForm({ ...cancelForm, initiated_by_party: event.target.value })
                  }
                >
                  <option value="buyer">Buyer</option>
                  <option value="seller">Seller</option>
                  <option value="mutual">Mutual</option>
                  <option value="developer_default_process">Developer default process</option>
                </select>
              </Field>
              <Field label="Reason">
                <input
                  className="input"
                  required
                  value={cancelForm.reason}
                  onChange={(event) =>
                    setCancelForm({ ...cancelForm, reason: event.target.value })
                  }
                />
              </Field>
              <Field label="Notice date">
                <input
                  className="input"
                  type="date"
                  value={cancelForm.notice_date}
                  onChange={(event) =>
                    setCancelForm({ ...cancelForm, notice_date: event.target.value })
                  }
                />
              </Field>
              <Field label="Cure deadline">
                <input
                  className="input"
                  type="date"
                  value={cancelForm.cure_deadline}
                  onChange={(event) =>
                    setCancelForm({ ...cancelForm, cure_deadline: event.target.value })
                  }
                />
              </Field>
              <Field label="Forfeiture">
                <input
                  className="input"
                  value={cancelForm.forfeiture_amount}
                  onChange={(event) =>
                    setCancelForm({ ...cancelForm, forfeiture_amount: event.target.value })
                  }
                />
              </Field>
              <Field
                label="Refund due"
                hint="What is owed. Whether it was paid is a payment record this system does not have yet."
              >
                <input
                  className="input"
                  value={cancelForm.refund_due_amount}
                  onChange={(event) =>
                    setCancelForm({ ...cancelForm, refund_due_amount: event.target.value })
                  }
                />
              </Field>
              <div className="form-actions">
                <button className="button" type="submit" disabled={busy}>
                  Open cancellation
                </button>
                <button
                  className="button button-small"
                  type="button"
                  onClick={() => setCancelling(false)}
                >
                  Cancel
                </button>
              </div>
            </form>
          ) : null}

          <h3 className="section-heading">Legal timeline</h3>
          <LegalTimelineView
            timeline={sale.legal}
            canRecord={canRecordLegal}
            busy={busy}
            onReverse={(eventId, reason) =>
              run(
                () => sales.reverseLegalEvent(projectId, eventId, reason),
                "Withdrawn. Both records stay on the timeline.",
              )
            }
          />
          {canRecordLegal && sale.sale.status !== "draft" ? (
            <form
              className="form-grid"
              onSubmit={(event) => {
                event.preventDefault();
                void run(
                  () =>
                    sales.recordLegalEvent(projectId, sale.sale.id, {
                      event_type: legalForm.event_type,
                      event_date: legalForm.event_date,
                      ...(legalForm.authority_reference
                        ? { authority_reference: legalForm.authority_reference }
                        : {}),
                      ...(legalForm.document_reference
                        ? { document_reference: legalForm.document_reference }
                        : {}),
                    }),
                  "Recorded.",
                );
              }}
            >
              <Field label="Milestone">
                <select
                  className="input"
                  value={legalForm.event_type}
                  onChange={(event) =>
                    setLegalForm({ ...legalForm, event_type: event.target.value })
                  }
                >
                  {LEGAL_EVENT_TYPES.map((type) => (
                    <option key={type} value={type}>
                      {legalEventLabel(type)}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Date">
                <input
                  className="input"
                  type="date"
                  value={legalForm.event_date}
                  onChange={(event) =>
                    setLegalForm({ ...legalForm, event_date: event.target.value })
                  }
                />
              </Field>
              <Field label="Authority reference">
                <input
                  className="input"
                  value={legalForm.authority_reference}
                  onChange={(event) =>
                    setLegalForm({ ...legalForm, authority_reference: event.target.value })
                  }
                />
              </Field>
              <Field label="Document reference">
                <input
                  className="input"
                  value={legalForm.document_reference}
                  onChange={(event) =>
                    setLegalForm({ ...legalForm, document_reference: event.target.value })
                  }
                />
              </Field>
              <div className="form-actions">
                <button className="button" type="submit" disabled={busy}>
                  Record milestone
                </button>
              </div>
            </form>
          ) : null}

          {sale.cancellation ? (
            <>
              <h3 className="section-heading">Cancellation</h3>
              <div className="chip-list">
                <Badge tone="neutral">{cancellationLabel(sale.cancellation.status)}</Badge>
                {sale.cancellation.legal_withdrawal_required ? (
                  <span className="chip">
                    Registry withdrawal: {sale.cancellation.legal_withdrawal_status}
                  </span>
                ) : null}
              </div>
              <dl className="reference-list">
                <Line label="Initiated by" value={sale.cancellation.initiated_by_party} />
                <Line label="Reason" value={sale.cancellation.reason} />
                <Line label="Notice" value={sale.cancellation.notice_date} />
                <Line label="Cure deadline" value={sale.cancellation.cure_deadline} />
                <Money label="Forfeiture" value={sale.cancellation.forfeiture_amount} />
                <Money label="Refund due" value={sale.cancellation.refund_due_amount} />
                <Line
                  label="Financial approval"
                  value={
                    sale.cancellation.financial_approval_required
                      ? (sale.cancellation.financial_approved_at ?? "Outstanding")
                      : "Not required"
                  }
                />
                <Line label="Unit returned" value={sale.cancellation.unit_return_date} />
              </dl>
              <p className="footnote">
                A refund due is what the contract says is owed. Whether it has been paid is a
                payment record this system does not have yet.
              </p>
              <div className="chip-list">
                {canApprove &&
                sale.cancellation.financial_approval_required &&
                sale.cancellation.financial_approved_at === null ? (
                  <button
                    className="button button-small"
                    type="button"
                    disabled={busy}
                    onClick={() => {
                      const reason = window.prompt("Why are these terms approved?");
                      if (reason && sale.cancellation) {
                        void run(
                          () =>
                            sales.approveCancellationTerms(
                              projectId,
                              sale.cancellation!.id,
                              reason,
                            ),
                          "Financial terms approved.",
                        );
                      }
                    }}
                  >
                    Approve financial terms
                  </button>
                ) : null}
                {canCancel && sale.cancellation.status !== "completed" ? (
                  <>
                    {(CANCELLATION_NEXT[sale.cancellation.status] ?? []).map((step) => (
                      <button
                        key={step}
                        className="button button-small"
                        type="button"
                        disabled={busy}
                        onClick={() =>
                          void run(
                            () =>
                              sales.advanceCancellation(projectId, sale.cancellation!.id, {
                                to_status: step,
                              }),
                            `Moved to ${cancellationLabel(step).toLowerCase()}.`,
                          )
                        }
                      >
                        {cancellationLabel(step)}
                      </button>
                    ))}
                    {sale.cancellation.status === "ready_for_unit_return" ? (
                      <button
                        className="button button-small button-primary"
                        type="button"
                        disabled={busy}
                        onClick={() =>
                          void run(
                            () =>
                              sales.completeCancellation(projectId, sale.cancellation!.id),
                            "Contract cancelled. The unit is returned and needs repricing.",
                          )
                        }
                      >
                        Complete and return the unit
                      </button>
                    ) : null}
                  </>
                ) : null}
              </div>
            </>
          ) : null}

          {sale.handover ? (
            <>
              <h3 className="section-heading">Handover</h3>
              <HandoverView
                detail={sale.handover}
                clearanceRoles={clearanceRoles}
                busy={busy}
                canRunHandover={canWriteSale}
                onGrant={(type, reference) =>
                  run(
                    () =>
                      sales.grantClearance(projectId, sale.handover!.handover.id, type, reference),
                    "Clearance given.",
                  )
                }
                onRevoke={(type, reason) =>
                  run(
                    () =>
                      sales.revokeClearance(projectId, sale.handover!.handover.id, type, reason),
                    "Clearance withdrawn.",
                  )
                }
                onComplete={(body) =>
                  run(
                    () => sales.completeHandover(projectId, sale.handover!.handover.id, body),
                    "Handed over.",
                  )
                }
              />
            </>
          ) : null}
        </>
      ) : null}
    </Panel>
  );
}
