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
  Stat,
  StatRow,
  SubPanel,
  TableScroll,
  Timeline,
  TimelineItem,
} from "@/components/ui";
import { useCurrencyCode } from "@/lib/currency";
import { businessDate, money } from "@/lib/format";
import { statusLabel, statusTone } from "@/components/projects/inventory/statusLabels";
import {
  ADJUSTMENT_TYPES,
  RATE_ADJUSTMENTS,
  adjustmentLabel,
  cancellationLabel,
  cancellationTone,
  clearanceLabel,
  exceptionLabel,
  exceptionTone,
  gateLabel,
  gateTone,
  handoverLabel,
  handoverTone,
  kycLabel,
  kycTone,
  legalEventLabel,
  reservationLabel,
  reservationTone,
  saleLabel,
  saleTone,
  treatmentLabel,
} from "@/components/projects/sales/labels";

/**
 * One deal file: this buyer, this unit, this price, and how far it has got.
 *
 * Deliberately one record rather than six screens. A reservation, an SPA, a
 * legal timeline, a cancellation and a handover are five records of one
 * transaction, and somebody answering "where is unit 101?" should not have to
 * visit five pages to find out. They are five sections here rather than one
 * long scroll, because the person asking is usually one of five teams and only
 * needs their own.
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
  termination_pending_approval: ["withdrawal_pending", "ready_for_unit_return", "withdrawn"],
  withdrawal_pending: ["ready_for_unit_return"],
  ready_for_unit_return: ["withdrawn"],
};

/** What the reason dialog is currently asking for, and what to do with it. */
type Ask = {
  title: string;
  label: string;
  hint?: string;
  confirmLabel: string;
  run: (value: string) => void;
};

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function PartyList({ parties }: { parties: ClientParty[] }) {
  if (parties.length === 0) {
    return (
      <EmptyState
        title="No buyers recorded yet"
        hint="A unit cannot be committed until the buyer shares total 1.000000."
      />
    );
  }
  const showsIdentity = "identity_document_number" in (parties[0] ?? {});
  return (
    <TableScroll label="Buyer parties">
      <thead>
        <tr>
          <th scope="col">Name as identification</th>
          <th scope="col">Role</th>
          <th scope="col" className="num">
            Share
          </th>
          <th scope="col">Nationality</th>
          {showsIdentity ? <th scope="col">Identity document</th> : null}
        </tr>
      </thead>
      <tbody>
        {parties.map((party) => (
          <tr key={party.id}>
            <th scope="row">{party.name_as_identification}</th>
            <td>{party.party_role === "purchaser" ? "Purchaser" : "Joint purchaser"}</td>
            <td className="num">{party.share_fraction}</td>
            <td>{party.nationality_code ?? "—"}</td>
            {"identity_document_number" in party ? (
              <td className="mono">
                {party.identity_document_type ?? "—"} {party.identity_document_number ?? ""}
              </td>
            ) : null}
          </tr>
        ))}
      </tbody>
    </TableScroll>
  );
}

/**
 * The legal milestones, in the order they happened.
 *
 * A withdrawn milestone stays on the timeline struck through rather than
 * disappearing, because it did happen and the correction that undid it is a
 * separate fact. The server decides which events still stand.
 */
function LegalTimelineView({
  timeline,
  canRecord,
  busy,
  onReverse,
}: {
  timeline: LegalTimeline;
  canRecord: boolean;
  busy: boolean;
  onReverse: (eventId: string) => void;
}) {
  const currencyCodeOf = useCurrencyCode();
  const effective = new Set(timeline.effective_event_ids);
  if (timeline.events.length === 0) {
    return (
      <EmptyState
        title="Nothing recorded yet"
        hint="Legal records each milestone as it happens."
      />
    );
  }
  return (
    <Timeline>
      {timeline.events.map((event) => {
        const stands = effective.has(event.id);
        const correction = event.reverses_event_id !== null;
        return (
          <TimelineItem
            key={event.id}
            title={legalEventLabel(event.event_type)}
            date={businessDate(event.event_date)}
            state={correction ? "void" : stands ? "done" : "void"}
            aside={
              correction ? (
                <Badge tone="muted">Correction</Badge>
              ) : stands ? (
                <Badge tone="success">Stands</Badge>
              ) : (
                <Badge tone="muted">Withdrawn</Badge>
              )
            }
            detail={
              <>
                <span className="subtle">
                  {[
                    event.authority_reference ? `Authority ${event.authority_reference}` : null,
                    event.document_reference ? `Document ${event.document_reference}` : null,
                    event.fee_amount
                      ? `Fee ${money(event.fee_amount, currencyCodeOf(event.currency_id))}`
                      : null,
                  ]
                    .filter(Boolean)
                    .join(" · ") || "No references recorded."}
                </span>
                {canRecord && !correction && stands ? (
                  <div className="button-row">
                    <Button
                      small
                      variant="quiet"
                      disabled={busy}
                      onClick={() => onReverse(event.id)}
                    >
                      Withdraw this milestone
                    </Button>
                  </div>
                ) : null}
              </>
            }
          />
        );
      })}
    </Timeline>
  );
}

/**
 * Handover: three clearances, each somebody else's to give, and the completion
 * that only happens once all of them are in.
 */
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
  onGrant: (type: string) => void;
  onRevoke: (type: string) => void;
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
      <section>
        <SectionHeader title="Progress" />
        <KeyValueGrid columns={3}>
          <KeyValue
            label="Status"
            value={
              <Badge tone={handoverTone(detail.handover.status)}>
                {handoverLabel(detail.handover.status)}
              </Badge>
            }
          />
          <KeyValue label="Readiness" mono value={businessDate(detail.handover.readiness_date)} />
          <KeyValue label="Inspection" mono value={businessDate(detail.handover.inspection_date)} />
          <KeyValue label="Snagging" value={detail.handover.snag_status} />
          <KeyValue
            label="Client notice"
            mono
            value={businessDate(detail.handover.client_notice_date)}
          />
          <KeyValue
            label="Scheduled"
            mono
            value={businessDate(detail.handover.scheduled_handover_date)}
          />
          <KeyValue label="Handed over" mono value={businessDate(detail.handover.handover_date)} />
          <KeyValue
            label="Acceptance document"
            value={detail.handover.acceptance_document_reference}
          />
        </KeyValueGrid>
      </section>

      <section>
        <SectionHeader
          title="Clearances"
          description="Three departments, three sign-offs. None of them is anybody else's to give."
        />
        <TableScroll label="Handover clearances">
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
                      <Badge tone="warning">Pending</Badge>
                    )}
                  </td>
                  <td className="mono">{clearance?.evidence_reference ?? "—"}</td>
                  <td>
                    {!mine ? (
                      <span className="subtle">Another team&rsquo;s to give</span>
                    ) : clearance?.status === "cleared" ? (
                      <Button small variant="quiet" disabled={busy} onClick={() => onRevoke(type)}>
                        Withdraw
                      </Button>
                    ) : (
                      <Button small disabled={busy} onClick={() => onGrant(type)}>
                        Give clearance
                      </Button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </TableScroll>
      </section>

      {detail.blockers.length > 0 ? (
        <Notice tone="info">Still outstanding: {detail.blockers.join("; ")}.</Notice>
      ) : null}

      {canRunHandover && detail.handover.status !== "handed_over" ? (
        <SubPanel title="Complete the handover">
          <form
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
            <div className="form-grid">
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
              <FormActions>
                <Button variant="primary" type="submit" disabled={busy || !ready}>
                  Complete handover
                </Button>
              </FormActions>
            </div>
          </form>
        </SubPanel>
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
  const [section, setSection] = useState("deal");
  const [ask, setAsk] = useState<Ask | null>(null);
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

  const currencyCodeOf = useCurrencyCode();
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

  /**
   * Ask for the reason an action needs, then run it.
   *
   * Almost everything on this screen is somebody's decision, and the server
   * stores the reason beside the change. Collecting it in a labelled dialog
   * rather than a browser prompt means the person can see what they are being
   * asked about while they answer.
   */
  const askThen = (
    prompt: Omit<Ask, "run">,
    action: (reason: string) => Promise<unknown>,
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

  if (error && reservation === null && sale === null) {
    return (
      <Drawer title="Deal" onClose={onClose}>
        <Notice tone="error">{error}</Notice>
      </Drawer>
    );
  }

  if (reservation === null && sale === null) {
    return (
      <Drawer title="Loading the deal…" onClose={onClose}>
        <Loading label="Loading the deal…" lines={5} />
      </Drawer>
    );
  }

  const terms = reservation?.reservation ?? null;
  const preparing = terms !== null && ["draft", "deposit_pending"].includes(terms.status);
  const live = terms !== null && ["active", "extended"].includes(terms.status);
  // A live reservation whose price lock has run out cannot proceed to contract
  // and cannot be edited either. The explicit re-quote is the way out, and the
  // screen offers it rather than leaving the operator at a dead end.
  const lockExpired = terms !== null && terms.price_locked_until < today();
  const isRate = RATE_ADJUSTMENTS.has(adjustment.adjustment_type);
  // Each record names its own denomination; nothing is inherited from the
  // project. The deposit may be taken in a different currency than the quote.
  const quoteCode = currencyCodeOf(terms?.currency_id);
  const depositCode = currencyCodeOf(terms?.deposit_currency_id);
  const saleCode = currencyCodeOf(sale?.sale.currency_id);

  const sections = [
    { key: "deal", label: "Reservation" },
    ...(sale ? [{ key: "contract", label: "Contract" }] : []),
    ...(sale ? [{ key: "legal", label: "Legal" }] : []),
    ...(sale?.cancellation ? [{ key: "closure", label: "Cancellation" }] : []),
    ...(sale?.handover ? [{ key: "handover", label: "Handover" }] : []),
  ];
  const activeSection = sections.some((entry) => entry.key === section) ? section : "deal";

  return (
    <Drawer
      eyebrow="Deal file"
      title={
        sale
          ? `${sale.sale.sale_number}${sale.sale.spa_number ? ` · ${sale.sale.spa_number}` : ""}`
          : (terms?.reservation_number ?? "Deal")
      }
      subtitle="One buyer, one unit, one price, and how far it has got."
      meta={
        <>
          {terms ? (
            <Badge tone={reservationTone(terms.status)}>{reservationLabel(terms.status)}</Badge>
          ) : null}
          {sale ? (
            <Badge tone={saleTone(sale.sale.status)}>{saleLabel(sale.sale.status)}</Badge>
          ) : null}
          {sale ? (
            <Badge tone={statusTone(sale.legal.legal_status)}>
              {statusLabel(sale.legal.legal_status)}
            </Badge>
          ) : null}
          {sale?.handover ? (
            <Badge tone={handoverTone(sale.handover.handover.status)}>
              {handoverLabel(sale.handover.handover.status)}
            </Badge>
          ) : null}
        </>
      }
      tabs={sections}
      activeTab={activeSection}
      onSelectTab={setSection}
      onClose={onClose}
    >
      {error ? <Notice tone="error">{error}</Notice> : null}
      {notice ? <Notice tone="success">{notice}</Notice> : null}

      {activeSection === "deal" ? (
        <>
          <section>
            <SectionHeader title="Buyer" />
            {client ? (
              <>
                <KeyValueGrid columns={3}>
                  <KeyValue
                    label="Client"
                    value={`${client.client_number} · ${client.display_name}`}
                  />
                  <KeyValue
                    label="Identity checks"
                    value={
                      <Badge tone={kycTone(client.kyc_status)}>{kycLabel(client.kyc_status)}</Badge>
                    }
                  />
                  <KeyValue
                    label="Buyer shares"
                    mono
                    value={
                      shares === null
                        ? null
                        : `${shares}${shares === "1.000000" ? "" : " — not yet a whole unit"}`
                    }
                  />
                  {"email" in client ? <KeyValue label="Email" value={client.email} /> : null}
                  {"phone" in client ? <KeyValue label="Phone" value={client.phone} /> : null}
                  {"address" in client ? <KeyValue label="Address" value={client.address} /> : null}
                </KeyValueGrid>
                <h4 className="section-heading">Parties</h4>
                <PartyList parties={parties} />
              </>
            ) : (
              <EmptyState
                title="Buyer not visible"
                hint="You may see this deal but not the buyer behind it."
              />
            )}
          </section>

          {terms ? (
            <>
              <section>
                <SectionHeader title="Reservation" />
                <ul className="chip-list">
                  {reservation?.closure_required ? (
                    <li>
                      <Badge tone="danger">Expired — closure required</Badge>
                    </li>
                  ) : null}
                  <li className="chip">
                    <span className="chip-label">Deposit</span>
                    <Badge tone={gateTone(terms.deposit_gate_status)}>
                      {gateLabel(terms.deposit_gate_status)}
                    </Badge>
                  </li>
                  <li className="chip">
                    <span className="chip-label">Approval</span>
                    <Badge tone={exceptionTone(terms.exception_approval_status)}>
                      {exceptionLabel(terms.exception_approval_status)}
                    </Badge>
                  </li>
                </ul>
                <KeyValueGrid columns={3}>
                  <KeyValue label="Number" mono value={terms.reservation_number} />
                  <KeyValue label="Reserved on" mono value={businessDate(terms.reservation_date)} />
                  <KeyValue label="Expires" mono value={businessDate(terms.expires_on)} />
                  <KeyValue
                    label="Price locked until"
                    mono
                    value={businessDate(terms.price_locked_until)}
                  />
                  <KeyValue label="Channel" value={terms.sales_channel_code} />
                  <KeyValue label="Branch" value={terms.sales_branch_code} />
                  <KeyValue
                    label="Deposit required"
                    mono
                    value={money(terms.deposit_required_amount, depositCode)}
                  />
                  <KeyValue
                    label="Deposit evidence"
                    value={terms.deposit_confirmation_reference}
                  />
                </KeyValueGrid>
                {lockExpired && live ? (
                  <Notice tone="warning">
                    The price lock on this reservation ran out on{" "}
                    {businessDate(terms.price_locked_until)}. It cannot go to contract or be
                    edited until it is re-quoted at the unit&rsquo;s current price.
                  </Notice>
                ) : null}
              </section>

              <section>
                <SectionHeader
                  title="Quote"
                  description="Every figure here was computed by the server. The browser does no pricing arithmetic."
                />
                <StatRow>
                  <Stat
                    label="Net contract price"
                    value={money(terms.net_contract_price_ex_tax, quoteCode)}
                  />
                  <Stat label="Tax" value={money(terms.tax_total, quoteCode)} small />
                  <Stat
                    label="Total buyer payable"
                    value={money(terms.total_buyer_payable, quoteCode)}
                  />
                </StatRow>
                <h4 className="section-heading">How it was reached</h4>
                <KeyValueGrid columns={3}>
                  <KeyValue
                    label="Approved list price"
                    mono
                    value={money(terms.reference_price_ex_tax, quoteCode)}
                  />
                  <KeyValue
                    label="Paid upgrades"
                    mono
                    value={money(terms.paid_upgrade_amount, quoteCode)}
                  />
                  <KeyValue
                    label="Payment plan adjustment"
                    mono
                    value={money(terms.payment_plan_adjustment_amount, quoteCode)}
                  />
                  <KeyValue
                    label="Gross quoted"
                    mono
                    value={money(terms.gross_quoted_price_ex_tax, quoteCode)}
                  />
                  <KeyValue
                    label="Cash discount"
                    mono
                    value={money(terms.cash_discount_amount, quoteCode)}
                  />
                  <KeyValue
                    label="Seller credit"
                    mono
                    value={money(terms.seller_credit_amount, quoteCode)}
                  />
                  <KeyValue
                    label="Net contract price"
                    mono
                    value={money(terms.net_contract_price_ex_tax, quoteCode)}
                  />
                  <KeyValue
                    label="Seller costs"
                    mono
                    value={money(terms.seller_cost_total, quoteCode)}
                  />
                  <KeyValue
                    label="Effective net revenue"
                    mono
                    value={money(terms.effective_net_revenue_preview, quoteCode)}
                  />
                  <KeyValue label="Buyer fees" mono value={money(terms.buyer_fee_total, quoteCode)} />
                </KeyValueGrid>
                <p className="footnote">
                  Seller costs sit beside the contract price and never inside it: a package the
                  seller absorbs does not reduce what the buyer contracts to pay.
                </p>
                {terms.exception_approval_required ? (
                  <Notice tone="warning">
                    {terms.exception_reason ?? "This quote needs sanctioning."}{" "}
                    {terms.exception_required_role
                      ? `Only ${terms.exception_required_role.replace("_", " ")} may approve it.`
                      : ""}
                  </Notice>
                ) : null}
              </section>

              <section>
                <SectionHeader title="Commercial inputs" />
                {reservation && reservation.adjustments.length > 0 ? (
                  <TableScroll label="Commercial inputs">
                    <thead>
                      <tr>
                        <th scope="col">Input</th>
                        <th scope="col">Effect</th>
                        <th scope="col" className="num">
                          Rate
                        </th>
                        <th scope="col" className="num">
                          Amount
                        </th>
                        <th scope="col">Reason</th>
                      </tr>
                    </thead>
                    <tbody>
                      {reservation.adjustments.map((item) => (
                        <tr key={item.id}>
                          <th scope="row">{adjustmentLabel(item.adjustment_type)}</th>
                          <td>{treatmentLabel(item.treatment)}</td>
                          <td className="num">{item.rate_fraction ?? "—"}</td>
                          <td className="num">{money(item.amount, quoteCode)}</td>
                          <td>{item.reason ?? "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </TableScroll>
                ) : (
                  <EmptyState
                    title="No adjustments"
                    hint="The quote is the approved list price."
                  />
                )}

                {canPrepare && preparing ? (
                  <SubPanel title="Record a commercial input">
                    <form
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
                      <div className="form-grid form-grid-3">
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
                            onChange={(event) =>
                              setAdjustment({ ...adjustment, value: event.target.value })
                            }
                          />
                        </Field>
                        <Field label="Reason">
                          <input
                            className="input"
                            value={adjustment.reason}
                            onChange={(event) =>
                              setAdjustment({ ...adjustment, reason: event.target.value })
                            }
                          />
                        </Field>
                        <FormActions>
                          <Button type="submit" disabled={busy}>
                            Record and re-quote
                          </Button>
                        </FormActions>
                      </div>
                    </form>
                  </SubPanel>
                ) : null}
              </section>

              <section>
                <SectionHeader title="What happens next" />
                <ButtonRow>
                  {canPrepare &&
                  (preparing || live) &&
                  terms.exception_approval_status === "pending" ? (
                    <Button
                      disabled={busy}
                      onClick={() =>
                        askThen(
                          {
                            title: "Submit this quote for approval",
                            label: "Why is this exception justified?",
                            confirmLabel: "Submit",
                          },
                          (reason) => sales.submitException(projectId, terms.id, reason),
                          "Put forward for sanction.",
                        )
                      }
                    >
                      Submit for approval
                    </Button>
                  ) : null}
                  {canApprove && terms.exception_approval_status === "submitted" ? (
                    <>
                      <Button
                        variant="primary"
                        disabled={busy}
                        onClick={() =>
                          askThen(
                            {
                              title: "Approve this exception",
                              label: "Why is this approved?",
                              confirmLabel: "Approve",
                            },
                            (reason) =>
                              sales.decideException(projectId, terms.id, true, reason),
                            "Approved.",
                          )
                        }
                      >
                        Approve exception
                      </Button>
                      <Button
                        variant="danger"
                        disabled={busy}
                        onClick={() =>
                          askThen(
                            {
                              title: "Refuse this exception",
                              label: "Why is this refused?",
                              confirmLabel: "Refuse",
                            },
                            (reason) =>
                              sales.decideException(projectId, terms.id, false, reason),
                            "Refused.",
                          )
                        }
                      >
                        Refuse exception
                      </Button>
                    </>
                  ) : null}
                  {canWriteSale && preparing && terms.deposit_gate_status === "pending" ? (
                    <Button
                      disabled={busy}
                      onClick={() =>
                        askThen(
                          {
                            title: "Record deposit evidence",
                            label: "Reference for the deposit evidence",
                            hint: "This attests that evidence exists. It is not a receipt.",
                            confirmLabel: "Record",
                          },
                          (reference) => sales.confirmDeposit(projectId, terms.id, reference),
                          "Deposit evidence recorded. This is not a receipt.",
                        )
                      }
                    >
                      Record deposit evidence
                    </Button>
                  ) : null}
                  {canApprove && terms.deposit_gate_status === "pending" ? (
                    <Button
                      disabled={busy}
                      onClick={() =>
                        askThen(
                          {
                            title: "Waive the deposit",
                            label: "Why is the deposit being waived?",
                            confirmLabel: "Waive",
                          },
                          (reason) => sales.waiveDeposit(projectId, terms.id, reason),
                          "Deposit waived.",
                        )
                      }
                    >
                      Waive deposit
                    </Button>
                  ) : null}
                  {canPrepare && preparing ? (
                    <Button
                      variant="primary"
                      disabled={busy}
                      onClick={() =>
                        void run(
                          () => sales.activateReservation(projectId, terms.id),
                          "The unit is reserved for this buyer.",
                        )
                      }
                    >
                      Activate reservation
                    </Button>
                  ) : null}
                  {canPrepare && live && lockExpired ? (
                    <Button
                      variant="primary"
                      disabled={busy}
                      onClick={() =>
                        askThen(
                          {
                            title: "Re-quote this reservation",
                            label: "Why is this reservation being re-quoted?",
                            hint: "The quote is re-run at the unit's current price and any approval it had is withdrawn.",
                            confirmLabel: "Re-quote",
                          },
                          (reason) => sales.requoteReservation(projectId, terms.id, reason),
                          "Re-quoted at the unit's current price. Any approval it had is withdrawn.",
                        )
                      }
                    >
                      Re-quote
                    </Button>
                  ) : null}
                  {canWriteSale && live && !lockExpired && sale === null ? (
                    <Button
                      variant="primary"
                      disabled={busy}
                      onClick={() =>
                        void run(
                          () => sales.createContract(projectId, { reservation_id: terms.id }),
                          "Contract drafted at the reservation's frozen price.",
                        )
                      }
                    >
                      Draw up contract
                    </Button>
                  ) : null}
                  {canPrepare && live ? (
                    <Button
                      variant="danger"
                      disabled={busy}
                      onClick={() =>
                        askThen(
                          {
                            title: "Cancel this reservation",
                            label: "Why is the reservation being cancelled?",
                            confirmLabel: "Cancel reservation",
                          },
                          (reason) => sales.cancelReservation(projectId, terms.id, reason),
                          "Reservation cancelled.",
                        )
                      }
                    >
                      Cancel reservation
                    </Button>
                  ) : null}
                  {canPrepare && reservation?.closure_required ? (
                    <Button
                      disabled={busy}
                      onClick={() =>
                        void run(
                          () => sales.expireReservation(projectId, terms.id),
                          "Reservation closed as expired.",
                        )
                      }
                    >
                      Close as expired
                    </Button>
                  ) : null}
                </ButtonRow>
              </section>
            </>
          ) : null}
        </>
      ) : null}

      {activeSection === "contract" && sale ? (
        <>
          <section>
            <SectionHeader title="Sale contract" />
            <StatRow>
              <Stat
                label="Total contract price"
                value={money(sale.sale.total_contract_price, saleCode)}
              />
              <Stat
                label="Net of tax"
                value={money(sale.sale.net_contract_price_ex_tax, saleCode)}
                small
              />
              <Stat label="Tax" value={money(sale.sale.tax_total, saleCode)} small />
              <Stat
                label="Effective net revenue"
                value={money(sale.sale.effective_net_revenue_snapshot, saleCode)}
                small
                note="After seller costs"
              />
            </StatRow>
            <KeyValueGrid columns={3}>
              <KeyValue label="Sale number" mono value={sale.sale.sale_number} />
              <KeyValue label="SPA number" mono value={sale.sale.spa_number} />
              <KeyValue label="Contract date" mono value={businessDate(sale.sale.contract_date)} />
              <KeyValue
                label="Seller costs"
                mono
                value={money(sale.sale.seller_cost_total, saleCode)}
              />
              <KeyValue
                label="First payment"
                value={
                  <Badge tone={gateTone(sale.sale.first_payment_gate_status)}>
                    {gateLabel(sale.sale.first_payment_gate_status)}
                  </Badge>
                }
              />
              <KeyValue
                label="Legal standing"
                value={
                  <Badge tone={statusTone(sale.legal.legal_status)}>
                    {statusLabel(sale.legal.legal_status)}
                  </Badge>
                }
              />
            </KeyValueGrid>
            <p className="footnote">
              Frozen at submission. Changing these terms means cancelling the pending contract,
              re-quoting the reservation and obtaining the approvals again.
            </p>
          </section>

          <section>
            <SectionHeader title="Contract parties" />
            <PartyList parties={sale.parties as unknown as ClientParty[]} />
          </section>

          {sale.tax_lines.length > 0 ? (
            <section>
              <SectionHeader
                title="Frozen taxes"
                description="The rates that applied on the contract date, kept whatever changes since."
              />
              <TableScroll label="Frozen tax lines">
                <thead>
                  <tr>
                    <th scope="col">Tax</th>
                    <th scope="col" className="num">
                      Rate
                    </th>
                    <th scope="col">Basis</th>
                    <th scope="col" className="num">
                      Taxable
                    </th>
                    <th scope="col" className="num">
                      Amount
                    </th>
                    <th scope="col">Valid on</th>
                  </tr>
                </thead>
                <tbody>
                  {sale.tax_lines.map((line) => (
                    <tr key={line.id}>
                      <th scope="row">{line.label}</th>
                      <td className="num">{line.rate_fraction}</td>
                      <td>{line.calculation_basis}</td>
                      <td className="num">
                        {money(line.taxable_amount, currencyCodeOf(line.currency_id))}
                      </td>
                      <td className="num">
                        {money(line.tax_amount, currencyCodeOf(line.currency_id))}
                      </td>
                      <td className="mono nowrap">{businessDate(line.valid_on)}</td>
                    </tr>
                  ))}
                </tbody>
              </TableScroll>
            </section>
          ) : null}

          <section>
            <SectionHeader title="What happens next" />
            <ButtonRow>
              {canWriteSale && sale.sale.status === "draft" ? (
                <Button
                  variant="primary"
                  disabled={busy}
                  onClick={() =>
                    void run(
                      () => sales.submitContract(projectId, sale.sale.id),
                      "Submitted for signature. The unit is now contract pending.",
                    )
                  }
                >
                  Submit for signature
                </Button>
              ) : null}
              {canWriteSale && sale.sale.first_payment_gate_status === "pending" ? (
                <Button
                  disabled={busy}
                  onClick={() =>
                    askThen(
                      {
                        title: "Record first-payment evidence",
                        label: "Reference for the payment evidence",
                        hint: "This attests that evidence exists. It is not a receipt.",
                        confirmLabel: "Record",
                      },
                      (reference) =>
                        sales.confirmFirstPayment(projectId, sale.sale.id, reference),
                      "First-payment evidence recorded. This is not a receipt.",
                    )
                  }
                >
                  Record first-payment evidence
                </Button>
              ) : null}
              {canApprove && sale.sale.first_payment_gate_status === "pending" ? (
                <Button
                  disabled={busy}
                  onClick={() =>
                    askThen(
                      {
                        title: "Waive the first payment",
                        label: "Why is the first payment being waived?",
                        confirmLabel: "Waive",
                      },
                      (reason) => sales.waiveFirstPayment(projectId, sale.sale.id, reason),
                      "First payment waived.",
                    )
                  }
                >
                  Waive first payment
                </Button>
              ) : null}
              {canWriteSale && sale.sale.status === "signature_pending" ? (
                <Button
                  variant="primary"
                  disabled={busy}
                  onClick={() =>
                    void run(
                      () => sales.activateContract(projectId, sale.sale.id),
                      "The contract is live and the unit is contracted.",
                    )
                  }
                >
                  Activate contract
                </Button>
              ) : null}
              {canWriteSale && sale.sale.status === "active" && sale.handover === null ? (
                <Button
                  disabled={busy}
                  onClick={() =>
                    void run(
                      () => sales.createHandover(projectId, sale.sale.id),
                      "Handover opened with three clearances outstanding.",
                    )
                  }
                >
                  Open handover
                </Button>
              ) : null}
              {canCancel &&
              sale.cancellation === null &&
              ["signature_pending", "active"].includes(sale.sale.status) ? (
                <Button variant="danger" disabled={busy} onClick={() => setCancelling(true)}>
                  Start cancellation
                </Button>
              ) : null}
            </ButtonRow>

            {cancelling ? (
              <SubPanel title="Open a cancellation">
                <form
                  onSubmit={(event) => {
                    event.preventDefault();
                    void run(
                      () =>
                        sales.startCancellation(projectId, sale.sale.id, {
                          initiated_by_party: cancelForm.initiated_by_party,
                          reason: cancelForm.reason,
                          ...(cancelForm.notice_date
                            ? { notice_date: cancelForm.notice_date }
                            : {}),
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
                    ).then(() => {
                      setCancelling(false);
                      setSection("closure");
                    });
                  }}
                >
                  <div className="form-grid">
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
                        <option value="developer_default_process">
                          Developer default process
                        </option>
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
                    <FormActions>
                      <Button variant="primary" type="submit" disabled={busy}>
                        Open cancellation
                      </Button>
                      <Button onClick={() => setCancelling(false)}>Cancel</Button>
                    </FormActions>
                  </div>
                </form>
              </SubPanel>
            ) : null}
          </section>
        </>
      ) : null}

      {activeSection === "legal" && sale ? (
        <>
          <section>
            <SectionHeader
              title="Legal timeline"
              description="Each milestone as it was recorded. A withdrawal never deletes what it undoes."
            />
            <LegalTimelineView
              timeline={sale.legal}
              canRecord={canRecordLegal}
              busy={busy}
              onReverse={(eventId) =>
                askThen(
                  {
                    title: "Withdraw this milestone",
                    label: "Why is this event being withdrawn?",
                    hint: "Both records stay on the timeline.",
                    confirmLabel: "Withdraw",
                  },
                  (reason) => sales.reverseLegalEvent(projectId, eventId, reason),
                  "Withdrawn. Both records stay on the timeline.",
                )
              }
            />
          </section>

          {canRecordLegal && sale.sale.status !== "draft" ? (
            <SubPanel title="Record a milestone">
              <form
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
                <div className="form-grid">
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
                  <FormActions>
                    <Button variant="primary" type="submit" disabled={busy}>
                      Record milestone
                    </Button>
                  </FormActions>
                </div>
              </form>
            </SubPanel>
          ) : null}
        </>
      ) : null}

      {activeSection === "closure" && sale?.cancellation ? (
        <>
          <section>
            <SectionHeader title="Cancellation" />
            <ul className="chip-list">
              <li>
                <Badge tone={cancellationTone(sale.cancellation.status)}>
                  {cancellationLabel(sale.cancellation.status)}
                </Badge>
              </li>
              {sale.cancellation.legal_withdrawal_required ? (
                <li className="chip">
                  <span className="chip-label">Registry withdrawal</span>
                  <strong>{sale.cancellation.legal_withdrawal_status}</strong>
                </li>
              ) : null}
            </ul>
            <KeyValueGrid columns={3}>
              <KeyValue label="Initiated by" value={sale.cancellation.initiated_by_party} />
              <KeyValue label="Reason" value={sale.cancellation.reason} />
              <KeyValue label="Notice" mono value={businessDate(sale.cancellation.notice_date)} />
              <KeyValue
                label="Cure deadline"
                mono
                value={businessDate(sale.cancellation.cure_deadline)}
              />
              <KeyValue
                label="Forfeiture"
                mono
                value={money(sale.cancellation.forfeiture_amount, saleCode)}
              />
              <KeyValue
                label="Refund due"
                mono
                value={money(sale.cancellation.refund_due_amount, saleCode)}
              />
              <KeyValue
                label="Financial approval"
                value={
                  sale.cancellation.financial_approval_required
                    ? (sale.cancellation.financial_approved_at ?? "Outstanding")
                    : "Not required"
                }
              />
              <KeyValue
                label="Unit returned"
                mono
                value={businessDate(sale.cancellation.unit_return_date)}
              />
            </KeyValueGrid>
            <p className="footnote">
              A refund due is what the contract says is owed. Whether it has been paid is a
              payment record this system does not have yet.
            </p>
          </section>

          <section>
            <SectionHeader title="What happens next" />
            <ButtonRow>
              {canApprove &&
              sale.cancellation.financial_approval_required &&
              sale.cancellation.financial_approved_at === null ? (
                <Button
                  variant="primary"
                  disabled={busy}
                  onClick={() =>
                    askThen(
                      {
                        title: "Approve the financial terms",
                        label: "Why are these terms approved?",
                        confirmLabel: "Approve",
                      },
                      (reason) =>
                        sales.approveCancellationTerms(projectId, sale.cancellation!.id, reason),
                      "Financial terms approved.",
                    )
                  }
                >
                  Approve financial terms
                </Button>
              ) : null}
              {canCancel && sale.cancellation.status !== "completed" ? (
                <>
                  {(CANCELLATION_NEXT[sale.cancellation.status] ?? []).map((step) => (
                    <Button
                      key={step}
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
                    </Button>
                  ))}
                  {sale.cancellation.status === "ready_for_unit_return" ? (
                    <Button
                      variant="danger"
                      disabled={busy}
                      onClick={() =>
                        void run(
                          () => sales.completeCancellation(projectId, sale.cancellation!.id),
                          "Contract cancelled. The unit is returned and needs repricing.",
                        )
                      }
                    >
                      Complete and return the unit
                    </Button>
                  ) : null}
                </>
              ) : null}
            </ButtonRow>
          </section>
        </>
      ) : null}

      {activeSection === "handover" && sale?.handover ? (
        <HandoverView
          detail={sale.handover}
          clearanceRoles={clearanceRoles}
          busy={busy}
          canRunHandover={canWriteSale}
          onGrant={(type) =>
            askThen(
              {
                title: `Give the ${clearanceLabel(type).toLowerCase()} clearance`,
                label: "Reference for the evidence",
                confirmLabel: "Give clearance",
              },
              (reference) =>
                sales.grantClearance(projectId, sale.handover!.handover.id, type, reference),
              "Clearance given.",
            )
          }
          onRevoke={(type) =>
            askThen(
              {
                title: `Withdraw the ${clearanceLabel(type).toLowerCase()} clearance`,
                label: "Why is this clearance being withdrawn?",
                confirmLabel: "Withdraw",
              },
              (reason) =>
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
