"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, sales } from "@/lib/api";
import type {
  HandoverDetail,
  LegalTimeline,
  Reservation,
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
  FieldRow,
  FormActions,
  KeyValue,
  KeyValueGrid,
  Loading,
  Metric,
  MetricGroup,
  MoneyInput,
  Position,
  PositionFigure,
  Notice,
  PromptDialog,
  RateInput,
  SectionHeader,
  Steps,
  SubPanel,
  TableScroll,
  Timeline,
  TimelineItem,
  Waterfall,
  WaterfallRow,
} from "@/components/ui";
import type { DrawerFact } from "@/components/ui";
import { useCurrencyCode } from "@/lib/currency";
import { businessDate, fractionFromPercent, money, percent, todayISO } from "@/lib/format";
import { COLLECTION_READERS, hasAnyRole } from "@/lib/roles";
import { PlanSummary } from "@/components/projects/payments/PlanSummary";
import { DealCollections } from "@/components/projects/collections/DealCollections";
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
 * legal timeline, a payment plan, a cancellation and a handover are records of
 * one transaction, and somebody answering "where is unit 101?" should not have
 * to visit six pages to find out. They are sections of one file rather than one
 * long scroll, because the person asking is usually one of five teams and only
 * needs their own. The header carries what every one of them opened it for:
 * the contract price, what it is net of tax, the date, and the gate that is
 * holding it.
 *
 * Nothing in this file calculates. Every figure shown was computed by the
 * server: the discount, the tax, the contract price, the effective net revenue
 * and whether an approval is required. The browser sends inputs and displays
 * what comes back, so there is never a second implementation of the waterfall
 * quietly disagreeing with the first. The lifecycle strip likewise draws the
 * statuses the server returned; it decides nothing.
 *
 * Personal data is likewise the server's decision. A party arrives with an
 * identity document number or without the field at all, and this file renders
 * what it was given rather than deciding who deserves to see what. Collections
 * figures are requested only on behalf of a role the server would answer.
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

/** The columns a buyer party is shown by, whichever record it came from. */
type PartyRow = {
  id: string;
  party_role: string;
  name_as_identification: string;
  nationality_code: string | null;
  share_fraction: string;
  identity_document_type?: string | null;
  identity_document_number?: string | null;
};

/**
 * Where the deal has got to, drawn from the statuses the server returned.
 *
 * Four milestones every team recognises. A step is "done" when the server's
 * own status for that record says so and "current" while the record exists
 * and is still moving; a cancelled or expired record shows as neither, and the
 * badge beside the title says what happened instead.
 */
function lifecycle(terms: Reservation | null, sale: SaleDetail | null) {
  const state = (done: boolean, current: boolean): "done" | "current" | "pending" =>
    done ? "done" : current ? "current" : "pending";
  const reservationDone =
    sale !== null || (terms !== null && ["active", "extended", "converted"].includes(terms.status));
  const reservationCurrent = terms !== null && ["draft", "deposit_pending"].includes(terms.status);
  const contractDone = sale !== null && ["active", "termination_pending"].includes(sale.sale.status);
  const contractCurrent = sale !== null && ["draft", "signature_pending"].includes(sale.sale.status);
  const legal = sale?.legal.legal_status ?? "no_spa";
  const registeredDone = ["registered", "transfer_pending", "transferred"].includes(legal);
  const registeredCurrent = sale !== null && !registeredDone && legal !== "no_spa";
  const handoverDone = sale?.handover?.handover.status === "handed_over";
  const handoverCurrent = sale?.handover != null && !handoverDone;
  return [
    { key: "reserved", label: "Reserved", state: state(reservationDone, reservationCurrent) },
    { key: "contracted", label: "Contracted", state: state(contractDone, contractCurrent) },
    { key: "registered", label: "Registered", state: state(registeredDone, registeredCurrent) },
    { key: "handed_over", label: "Handed over", state: state(handoverDone, handoverCurrent) },
  ];
}

function PartyList({ parties }: { parties: PartyRow[] }) {
  if (parties.length === 0) {
    return (
      <EmptyState
        compact
        title="No buyers recorded yet"
        hint="A unit cannot be committed until the buyer shares total 1.000000."
      />
    );
  }
  const showsIdentity = "identity_document_number" in (parties[0] ?? {});
  return (
    <TableScroll label="Buyer parties" compact>
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
      <EmptyState compact title="Nothing recorded yet" hint="Legal records each milestone as it happens." />
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
                    event.fee_amount ? `Fee ${money(event.fee_amount, currencyCodeOf(event.currency_id))}` : null,
                  ]
                    .filter(Boolean)
                    .join(" · ") || "No references recorded."}
                </span>
                {canRecord && !correction && stands ? (
                  <div className="button-row">
                    <Button small variant="quiet" disabled={busy} onClick={() => onReverse(event.id)}>
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
    handover_date: detail.handover.handover_date ?? todayISO(),
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
  const ready = outstanding.length === 0 && form.handover_date !== "" && form.acceptance_document_reference !== "";

  return (
    <>
      <section>
        <SectionHeader
          title="Progress"
          actions={
            <Badge tone={handoverTone(detail.handover.status)}>{handoverLabel(detail.handover.status)}</Badge>
          }
        />
        <KeyValueGrid columns={4}>
          <KeyValue label="Readiness" mono value={businessDate(detail.handover.readiness_date)} />
          <KeyValue label="Inspection" mono value={businessDate(detail.handover.inspection_date)} />
          <KeyValue label="Snagging" value={detail.handover.snag_status} />
          <KeyValue label="Client notice" mono value={businessDate(detail.handover.client_notice_date)} />
          <KeyValue label="Scheduled" mono value={businessDate(detail.handover.scheduled_handover_date)} />
          <KeyValue label="Handed over" mono value={businessDate(detail.handover.handover_date)} />
          <KeyValue label="Acceptance document" value={detail.handover.acceptance_document_reference} />
          <KeyValue label="Keys" value={detail.handover.keys_reference} />
        </KeyValueGrid>
      </section>

      <section>
        <SectionHeader
          title="Clearances"
          description="Three departments, three sign-offs. None of them is anybody else's to give."
        />
        <TableScroll label="Handover clearances" compact>
          <thead>
            <tr>
              <th scope="col">Department</th>
              <th scope="col">Status</th>
              <th scope="col">Evidence</th>
              <th scope="col">
                <span className="visually-hidden">Action</span>
              </th>
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
            <FieldRow columns={3}>
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
                  onChange={(event) => setForm({ ...form, acceptance_document_reference: event.target.value })}
                />
              </Field>
              <Field label="Keys reference" optional>
                <input
                  className="input"
                  value={form.keys_reference}
                  onChange={(event) => setForm({ ...form, keys_reference: event.target.value })}
                />
              </Field>
            </FieldRow>
            <FormActions>
              <Button variant="primary" type="submit" disabled={busy || !ready}>
                Complete handover
              </Button>
            </FormActions>
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
  unitReference,
  onClose,
  onChanged,
}: {
  projectId: string;
  reservationId: string | null;
  saleId: string | null;
  roles: Set<string>;
  /** The unit the register row named, so the header can say it before the deal loads. */
  unitReference?: string | null;
  onClose: () => void;
  onChanged: () => Promise<void>;
}) {
  const [reservation, setReservation] = useState<ReservationDetail | null>(null);
  const [sale, setSale] = useState<SaleDetail | null>(null);
  const [client, setClient] = useState<SalesClient | null>(null);
  const [parties, setParties] = useState<PartyRow[]>([]);
  const [shares, setShares] = useState<string | null>(null);
  const [section, setSection] = useState<string | null>(null);
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
    event_date: todayISO(),
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
  const seesCollections = hasAnyRole(roles, COLLECTION_READERS);
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
      const clientId = loadedSale?.sale.client_id ?? loadedReservation?.reservation.client_id ?? null;
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
      // The server answers "not found" for a buyer this advisor was not
      // assigned, exactly as for one that never existed. Said plainly here.
      setError(
        caught instanceof ApiError && caught.status === 404
          ? "This deal is not visible to you. A Sales Advisor sees only the buyers assigned to them."
          : caught instanceof ApiError
            ? caught.message
            : "Could not load the deal.",
      );
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
  const askThen = (prompt: Omit<Ask, "run">, action: (reason: string) => Promise<unknown>, done: string) => {
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
      <Drawer eyebrow="Deal file" title={unitReference ?? "Deal"} onClose={onClose}>
        <Notice tone="error">{error}</Notice>
      </Drawer>
    );
  }

  if (reservation === null && sale === null) {
    return (
      <Drawer eyebrow="Deal file" title={unitReference ?? "Loading the deal…"} onClose={onClose}>
        <Loading label="Loading the deal…" shape="record" />
      </Drawer>
    );
  }

  const terms = reservation?.reservation ?? null;
  const preparing = terms !== null && ["draft", "deposit_pending"].includes(terms.status);
  const live = terms !== null && ["active", "extended"].includes(terms.status);
  // A live reservation whose price lock has run out cannot proceed to contract
  // and cannot be edited either. The explicit re-quote is the way out, and the
  // screen offers it rather than leaving the operator at a dead end.
  const lockExpired = terms !== null && terms.price_locked_until < todayISO();
  const isRate = RATE_ADJUSTMENTS.has(adjustment.adjustment_type);
  // Each record names its own denomination; nothing is inherited from the
  // project. The deposit may be taken in a different currency than the quote.
  const quoteCode = currencyCodeOf(terms?.currency_id);
  const depositCode = currencyCodeOf(terms?.deposit_currency_id);
  const saleCode = currencyCodeOf(sale?.sale.currency_id);

  const sections = [
    ...(terms ? [{ key: "commercial", label: "Commercial" }] : []),
    { key: "buyers", label: "Buyers" },
    ...(sale ? [{ key: "contract", label: "Contract" }] : []),
    ...(sale ? [{ key: "legal", label: "Legal" }] : []),
    ...(sale ? [{ key: "plan", label: "Payment plan" }] : []),
    ...(sale && seesCollections ? [{ key: "collections", label: "Collections" }] : []),
    ...(sale?.cancellation ? [{ key: "closure", label: "Cancellation" }] : []),
    ...(sale?.handover ? [{ key: "handover", label: "Handover" }] : []),
  ];
  const fallback = sale ? "contract" : "commercial";
  const activeSection =
    section !== null && sections.some((entry) => entry.key === section) ? section : fallback;

  const facts: DrawerFact[] = sale
    ? [
        { label: "Contract price", value: money(sale.sale.total_contract_price, saleCode), note: "Buyer payable" },
        { label: "Net of tax", value: money(sale.sale.net_contract_price_ex_tax, saleCode) },
        { label: "Contract date", value: businessDate(sale.sale.contract_date) },
        {
          label: "First payment",
          value: gateLabel(sale.sale.first_payment_gate_status),
          note: sale.sale.first_payment_required_amount
            ? money(sale.sale.first_payment_required_amount, saleCode)
            : undefined,
        },
      ]
    : terms
      ? [
          { label: "Net contract price", value: money(terms.net_contract_price_ex_tax, quoteCode), note: "Ex tax" },
          { label: "Total buyer payable", value: money(terms.total_buyer_payable, quoteCode) },
          { label: "Expires", value: businessDate(terms.expires_on) },
          {
            label: "Deposit",
            value: gateLabel(terms.deposit_gate_status),
            note: terms.deposit_required_amount ? money(terms.deposit_required_amount, depositCode) : undefined,
          },
        ]
      : [];

  return (
    <Drawer
      eyebrow="Deal file"
      title={
        sale
          ? `${sale.sale.sale_number}${sale.sale.spa_number ? ` · ${sale.sale.spa_number}` : ""}`
          : (terms?.reservation_number ?? "Deal")
      }
      subtitle={[unitReference ? `Unit ${unitReference}` : null, client?.display_name ?? null]
        .filter(Boolean)
        .join(" · ")}
      meta={
        <>
          {terms ? <Badge tone={reservationTone(terms.status)}>{reservationLabel(terms.status)}</Badge> : null}
          {sale ? <Badge tone={saleTone(sale.sale.status)}>{saleLabel(sale.sale.status)}</Badge> : null}
          {sale ? (
            <Badge tone={statusTone(sale.legal.legal_status)}>{statusLabel(sale.legal.legal_status)}</Badge>
          ) : null}
          {sale?.handover ? (
            <Badge tone={handoverTone(sale.handover.handover.status)}>
              {handoverLabel(sale.handover.handover.status)}
            </Badge>
          ) : null}
          {reservation?.closure_required ? <Badge tone="danger">Expired — closure required</Badge> : null}
        </>
      }
      facts={facts}
      tabs={sections}
      activeTab={activeSection}
      onSelectTab={setSection}
      onClose={onClose}
    >
      <Steps label="Where the deal has got to" steps={lifecycle(terms, sale)} />

      {error ? <Notice tone="error">{error}</Notice> : null}
      {notice ? <Notice tone="success">{notice}</Notice> : null}

      {activeSection === "commercial" && terms ? (
        <>
          <section>
            <SectionHeader
              title="Reservation"
              actions={
                <>
                  <Badge tone={gateTone(terms.deposit_gate_status)}>
                    Deposit {gateLabel(terms.deposit_gate_status).toLowerCase()}
                  </Badge>
                  <Badge tone={exceptionTone(terms.exception_approval_status)}>
                    Approval {exceptionLabel(terms.exception_approval_status).toLowerCase()}
                  </Badge>
                </>
              }
            />
            <KeyValueGrid columns={4}>
              <KeyValue label="Number" mono value={terms.reservation_number} />
              <KeyValue label="Reserved on" mono value={businessDate(terms.reservation_date)} />
              <KeyValue label="Expires" mono value={businessDate(terms.expires_on)} />
              <KeyValue label="Price locked until" mono value={businessDate(terms.price_locked_until)} />
              <KeyValue label="Channel" value={terms.sales_channel_code} />
              <KeyValue label="Branch" value={terms.sales_branch_code} />
              <KeyValue label="Deposit required" mono value={money(terms.deposit_required_amount, depositCode)} />
              <KeyValue label="Deposit evidence" value={terms.deposit_confirmation_reference} />
            </KeyValueGrid>
            {lockExpired && live ? (
              <Notice tone="warning">
                The price lock on this reservation ran out on {businessDate(terms.price_locked_until)}. It
                cannot go to contract or be edited until it is re-quoted at the unit&rsquo;s current price.
              </Notice>
            ) : null}
          </section>

          <section>
            <SectionHeader
              title="Quote"
              description="Every figure here was computed by the server. The browser does no pricing arithmetic."
            />
            <Position compact>
              <PositionFigure
                lead
                label="Net contract price"
                value={money(terms.net_contract_price_ex_tax, quoteCode)}
                note="Ex tax"
              />
              <PositionFigure label="Tax" value={money(terms.tax_total, quoteCode)} />
              <PositionFigure label="Buyer fees" value={money(terms.buyer_fee_total, quoteCode)} />
              <PositionFigure label="Total buyer payable" value={money(terms.total_buyer_payable, quoteCode)} />
            </Position>
            <h4 className="section-heading">How it was reached</h4>
            <Waterfall>
              <WaterfallRow label="Approved list price" note="Ex tax" amount={money(terms.reference_price_ex_tax, quoteCode)} />
              <WaterfallRow label="Paid upgrades" amount={money(terms.paid_upgrade_amount, quoteCode)} />
              <WaterfallRow label="Payment plan adjustment" amount={money(terms.payment_plan_adjustment_amount, quoteCode)} />
              <WaterfallRow label="Gross quoted price" note="Ex tax" amount={money(terms.gross_quoted_price_ex_tax, quoteCode)} kind="subtotal" />
              <WaterfallRow label="Cash discount" note="Reduces what the buyer pays" amount={money(terms.cash_discount_amount, quoteCode)} />
              <WaterfallRow label="Seller credit" amount={money(terms.seller_credit_amount, quoteCode)} />
              <WaterfallRow label="Net contract price" note="Ex tax" amount={money(terms.net_contract_price_ex_tax, quoteCode)} kind="total" />
            </Waterfall>
            <KeyValueGrid columns={3}>
              <KeyValue label="Seller costs" mono value={money(terms.seller_cost_total, quoteCode)} />
              <KeyValue label="Effective net revenue" mono value={money(terms.effective_net_revenue_preview, quoteCode)} />
              <KeyValue label="Buyer fees" mono value={money(terms.buyer_fee_total, quoteCode)} />
            </KeyValueGrid>
            <p className="footnote">
              Seller costs sit beside the contract price and never inside it: a package the seller
              absorbs does not reduce what the buyer contracts to pay.
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
              <TableScroll label="Commercial inputs" compact>
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
                    <th scope="col" className="cell-prose">
                      Reason
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {reservation.adjustments.map((item) => (
                    <tr key={item.id}>
                      <th scope="row">{adjustmentLabel(item.adjustment_type)}</th>
                      <td>{treatmentLabel(item.treatment)}</td>
                      <td className="num">{item.rate_fraction === null ? "—" : percent(item.rate_fraction)}</td>
                      <td className="num">{money(item.amount, quoteCode)}</td>
                      <td className="cell-prose">{item.reason ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </TableScroll>
            ) : (
              <EmptyState compact title="No adjustments" hint="The quote is the approved list price." />
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
                            ? { rate_fraction: fractionFromPercent(adjustment.value) }
                            : { amount: adjustment.value }),
                          ...(adjustment.reason ? { reason: adjustment.reason } : {}),
                        }),
                      "Recorded, and the quote re-run.",
                    );
                  }}
                >
                  <FieldRow columns={3}>
                    <Field label="Commercial input">
                      <select
                        className="input"
                        value={adjustment.adjustment_type}
                        onChange={(event) =>
                          setAdjustment({ ...adjustment, adjustment_type: event.target.value, value: "" })
                        }
                      >
                        {ADJUSTMENT_TYPES.map((type) => (
                          <option key={type} value={type}>
                            {adjustmentLabel(type)}
                          </option>
                        ))}
                      </select>
                    </Field>
                    {isRate ? (
                      <Field label="Rate" hint="Of the reference price. Five means five per cent.">
                        <RateInput
                          value={adjustment.value}
                          required
                          onChange={(value) => setAdjustment({ ...adjustment, value })}
                        />
                      </Field>
                    ) : (
                      <Field label="Amount">
                        <MoneyInput
                          code={quoteCode}
                          value={adjustment.value}
                          required
                          onChange={(value) => setAdjustment({ ...adjustment, value })}
                        />
                      </Field>
                    )}
                    <Field label="Reason" optional>
                      <input
                        className="input"
                        value={adjustment.reason}
                        onChange={(event) => setAdjustment({ ...adjustment, reason: event.target.value })}
                      />
                    </Field>
                  </FieldRow>
                  <FormActions>
                    <Button type="submit" disabled={busy}>
                      Record and re-quote
                    </Button>
                  </FormActions>
                </form>
              </SubPanel>
            ) : null}
          </section>

          <section>
            <SectionHeader title="What happens next" />
            <ButtonRow>
              {canPrepare && (preparing || live) && terms.exception_approval_status === "pending" ? (
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
                        (reason) => sales.decideException(projectId, terms.id, true, reason),
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
                        (reason) => sales.decideException(projectId, terms.id, false, reason),
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
                    void run(() => sales.expireReservation(projectId, terms.id), "Reservation closed as expired.")
                  }
                >
                  Close as expired
                </Button>
              ) : null}
            </ButtonRow>
          </section>
        </>
      ) : null}

      {activeSection === "buyers" ? (
        <section>
          <SectionHeader
            title="Buyer"
            actions={
              client ? <Badge tone={kycTone(client.kyc_status)}>{kycLabel(client.kyc_status)}</Badge> : undefined
            }
          />
          {client ? (
            <>
              <KeyValueGrid columns={3}>
                <KeyValue label="Client" value={`${client.client_number} · ${client.display_name}`} />
                <KeyValue
                  label="Buyer shares"
                  mono
                  value={shares === null ? null : `${shares}${shares === "1.000000" ? "" : " — not yet a whole unit"}`}
                />
                <KeyValue label="Preferred language" value={client.preferred_language_code} />
                {"email" in client ? <KeyValue label="Email" value={client.email} /> : null}
                {"phone" in client ? <KeyValue label="Phone" value={client.phone} /> : null}
                {"address" in client ? <KeyValue label="Address" value={client.address} /> : null}
              </KeyValueGrid>
              <h4 className="section-heading">Named parties</h4>
              <PartyList parties={parties} />
              {sale ? (
                <>
                  <h4 className="section-heading">Parties on the contract</h4>
                  <PartyList parties={sale.parties} />
                </>
              ) : null}
            </>
          ) : (
            <EmptyState title="Buyer not visible" hint="You may see this deal but not the buyer behind it." />
          )}
        </section>
      ) : null}

      {activeSection === "contract" && sale ? (
        <>
          <section>
            <SectionHeader
              title="Sale contract"
              actions={
                <Badge tone={gateTone(sale.sale.first_payment_gate_status)}>
                  First payment {gateLabel(sale.sale.first_payment_gate_status).toLowerCase()}
                </Badge>
              }
            />
            <Position compact>
              <PositionFigure lead label="Total contract price" value={money(sale.sale.total_contract_price, saleCode)} />
              <PositionFigure label="Net of tax" value={money(sale.sale.net_contract_price_ex_tax, saleCode)} />
              <PositionFigure label="Tax" value={money(sale.sale.tax_total, saleCode)} />
              <PositionFigure label="Buyer fees" value={money(sale.sale.buyer_fee_total, saleCode)} />
              <PositionFigure
                label="Effective net revenue"
                value={money(sale.sale.effective_net_revenue_snapshot, saleCode)}
                note="After seller costs"
              />
            </Position>
            <KeyValueGrid columns={4}>
              <KeyValue label="Sale number" mono value={sale.sale.sale_number} />
              <KeyValue label="SPA number" mono value={sale.sale.spa_number} />
              <KeyValue label="Contract date" mono value={businessDate(sale.sale.contract_date)} />
              <KeyValue label="Seller costs" mono value={money(sale.sale.seller_cost_total, saleCode)} />
              <KeyValue label="Cash discount" mono value={money(sale.sale.cash_discount_amount, saleCode)} />
              <KeyValue label="Seller credit" mono value={money(sale.sale.seller_credit_amount, saleCode)} />
              <KeyValue label="Channel" value={sale.sale.sales_channel_code} />
              <KeyValue
                label="Legal standing"
                value={
                  <Badge tone={statusTone(sale.legal.legal_status)}>{statusLabel(sale.legal.legal_status)}</Badge>
                }
              />
            </KeyValueGrid>
            <p className="footnote">
              Frozen at submission. Changing these terms means cancelling the pending contract,
              re-quoting the reservation and obtaining the approvals again.
            </p>
          </section>

          {sale.tax_lines.length > 0 ? (
            <section>
              <SectionHeader
                title="Frozen taxes"
                description="The rates that applied on the contract date, kept whatever changes since."
              />
              <TableScroll label="Frozen tax lines" compact>
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
                      <td className="num">{percent(line.rate_fraction)}</td>
                      <td>{line.calculation_basis}</td>
                      <td className="num">{money(line.taxable_amount, currencyCodeOf(line.currency_id))}</td>
                      <td className="num">{money(line.tax_amount, currencyCodeOf(line.currency_id))}</td>
                      <td className="figure">{businessDate(line.valid_on)}</td>
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
                      (reference) => sales.confirmFirstPayment(projectId, sale.sale.id, reference),
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
              {canCancel && sale.cancellation === null && ["signature_pending", "active"].includes(sale.sale.status) ? (
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
                          ...(cancelForm.notice_date ? { notice_date: cancelForm.notice_date } : {}),
                          ...(cancelForm.cure_deadline ? { cure_deadline: cancelForm.cure_deadline } : {}),
                          ...(cancelForm.forfeiture_amount ? { forfeiture_amount: cancelForm.forfeiture_amount } : {}),
                          ...(cancelForm.refund_due_amount ? { refund_due_amount: cancelForm.refund_due_amount } : {}),
                        }),
                      "Cancellation opened. The unit stays committed until it completes.",
                    ).then(() => {
                      setCancelling(false);
                      setSection("closure");
                    });
                  }}
                >
                  <FieldRow columns={2}>
                    <Field label="Initiated by">
                      <select
                        className="input"
                        value={cancelForm.initiated_by_party}
                        onChange={(event) => setCancelForm({ ...cancelForm, initiated_by_party: event.target.value })}
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
                        onChange={(event) => setCancelForm({ ...cancelForm, reason: event.target.value })}
                      />
                    </Field>
                  </FieldRow>
                  <FieldRow columns={4}>
                    <Field label="Notice date" optional>
                      <input
                        className="input"
                        type="date"
                        value={cancelForm.notice_date}
                        onChange={(event) => setCancelForm({ ...cancelForm, notice_date: event.target.value })}
                      />
                    </Field>
                    <Field label="Cure deadline" optional>
                      <input
                        className="input"
                        type="date"
                        value={cancelForm.cure_deadline}
                        onChange={(event) => setCancelForm({ ...cancelForm, cure_deadline: event.target.value })}
                      />
                    </Field>
                    <Field label="Forfeiture" optional>
                      <MoneyInput
                        code={saleCode}
                        value={cancelForm.forfeiture_amount}
                        onChange={(value) => setCancelForm({ ...cancelForm, forfeiture_amount: value })}
                      />
                    </Field>
                    <Field
                      label="Refund due"
                      optional
                      hint="What is owed. Whether it was paid is a payment record kept in Collections."
                    >
                      <MoneyInput
                        code={saleCode}
                        value={cancelForm.refund_due_amount}
                        onChange={(value) => setCancelForm({ ...cancelForm, refund_due_amount: value })}
                      />
                    </Field>
                  </FieldRow>
                  <FormActions>
                    <Button variant="primary" type="submit" disabled={busy}>
                      Open cancellation
                    </Button>
                    <Button onClick={() => setCancelling(false)}>Cancel</Button>
                  </FormActions>
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
              actions={
                <Badge tone={statusTone(sale.legal.legal_status)}>{statusLabel(sale.legal.legal_status)}</Badge>
              }
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
                        ...(legalForm.authority_reference ? { authority_reference: legalForm.authority_reference } : {}),
                        ...(legalForm.document_reference ? { document_reference: legalForm.document_reference } : {}),
                      }),
                    "Recorded.",
                  );
                }}
              >
                <FieldRow columns={4}>
                  <Field label="Milestone">
                    <select
                      className="input"
                      value={legalForm.event_type}
                      onChange={(event) => setLegalForm({ ...legalForm, event_type: event.target.value })}
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
                      onChange={(event) => setLegalForm({ ...legalForm, event_date: event.target.value })}
                    />
                  </Field>
                  <Field label="Authority reference" optional>
                    <input
                      className="input"
                      value={legalForm.authority_reference}
                      onChange={(event) => setLegalForm({ ...legalForm, authority_reference: event.target.value })}
                    />
                  </Field>
                  <Field label="Document reference" optional>
                    <input
                      className="input"
                      value={legalForm.document_reference}
                      onChange={(event) => setLegalForm({ ...legalForm, document_reference: event.target.value })}
                    />
                  </Field>
                </FieldRow>
                <FormActions>
                  <Button variant="primary" type="submit" disabled={busy}>
                    Record milestone
                  </Button>
                </FormActions>
              </form>
            </SubPanel>
          ) : null}
        </>
      ) : null}

      {activeSection === "plan" && sale ? (
        <section>
          <SectionHeader
            title="Payment plan"
            description="What the buyer agreed to pay, and when. Not what has been collected."
          />
          <PlanSummary projectId={projectId} saleId={sale.sale.id} />
        </section>
      ) : null}

      {activeSection === "collections" && sale && seesCollections ? (
        <section>
          <SectionHeader
            title="Collections"
            description="What actually arrived, where it was applied, and what is still owed."
          />
          <DealCollections projectId={projectId} saleId={sale.sale.id} />
        </section>
      ) : null}

      {activeSection === "closure" && sale?.cancellation ? (
        <>
          <section>
            <SectionHeader
              title="Cancellation"
              actions={
                <>
                  <Badge tone={cancellationTone(sale.cancellation.status)}>
                    {cancellationLabel(sale.cancellation.status)}
                  </Badge>
                  {sale.cancellation.legal_withdrawal_required ? (
                    <Badge tone="muted">Registry withdrawal {sale.cancellation.legal_withdrawal_status}</Badge>
                  ) : null}
                </>
              }
            />
            <MetricGroup compact>
              <Metric label="Forfeiture" value={money(sale.cancellation.forfeiture_amount, saleCode)} size="sm" />
              <Metric
                label="Refund due"
                value={money(sale.cancellation.refund_due_amount, saleCode)}
                note="What the contract says is owed"
                size="sm"
              />
              <Metric
                label="Financial approval"
                value={
                  sale.cancellation.financial_approval_required
                    ? sale.cancellation.financial_approved_at
                      ? "Approved"
                      : "Outstanding"
                    : "Not required"
                }
                size="sm"
              />
            </MetricGroup>
            <KeyValueGrid columns={4}>
              <KeyValue label="Initiated by" value={sale.cancellation.initiated_by_party} />
              <KeyValue label="Reason" value={sale.cancellation.reason} />
              <KeyValue label="Notice" mono value={businessDate(sale.cancellation.notice_date)} />
              <KeyValue label="Cure deadline" mono value={businessDate(sale.cancellation.cure_deadline)} />
              <KeyValue label="Unit returned" mono value={businessDate(sale.cancellation.unit_return_date)} />
            </KeyValueGrid>
            <p className="footnote">
              A refund due is what the contract says is owed. Whether it has been paid is recorded on
              the collections account.
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
                      (reason) => sales.approveCancellationTerms(projectId, sale.cancellation!.id, reason),
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
                          () => sales.advanceCancellation(projectId, sale.cancellation!.id, { to_status: step }),
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
              (reference) => sales.grantClearance(projectId, sale.handover!.handover.id, type, reference),
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
              (reason) => sales.revokeClearance(projectId, sale.handover!.handover.id, type, reason),
              "Clearance withdrawn.",
            )
          }
          onComplete={(body) =>
            run(() => sales.completeHandover(projectId, sale.handover!.handover.id, body), "Handed over.")
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
