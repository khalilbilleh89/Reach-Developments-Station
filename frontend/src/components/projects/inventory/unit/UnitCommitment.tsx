"use client";

import type { Reservation, SaleDetail } from "@/lib/api";
import {
  Badge,
  EmptyState,
  KeyValue,
  KeyValueGrid,
  Notice,
  SectionHeader,
  TableScroll,
  Timeline,
  TimelineItem,
} from "@/components/ui";
import { PlanSummary } from "@/components/projects/payments/PlanSummary";
import { useCurrencyCode } from "@/lib/currency";
import { businessDate, money } from "@/lib/format";
import {
  gateLabel,
  gateTone,
  handoverLabel,
  handoverTone,
  legalEventLabel,
  reservationLabel,
  reservationTone,
  saleLabel,
  saleTone,
} from "@/components/projects/sales/labels";

/**
 * The live commercial record on a unit: the reservation that holds it, the
 * contract that owns it, or neither. Both halves are the server's own records,
 * chosen by status, and either may be absent.
 */
export type Commitment = { reservation: Reservation | null; sale: SaleDetail | null };

/**
 * The deal on this unit, as inventory is allowed to see it.
 *
 * A read-only view: reserving, contracting, cancelling and handing over all
 * happen in Sales, on the deal file, where the whole transaction is in one
 * place. This exists so somebody looking at a unit is not left guessing why it
 * is not available.
 *
 * Buyer identity is shown only where the API returned it. A field the server
 * withheld is reported as withheld rather than blanked, because "not shown to
 * your role" and "not recorded" are different facts.
 */
export function UnitCommitment({
  projectId,
  commercialStatus,
  commitment,
}: {
  projectId: string;
  /** The unit's own commercial status, so a withheld record is not reported as no record. */
  commercialStatus: string;
  commitment: Commitment | null;
}) {
  const currencyCodeOf = useCurrencyCode();

  if (commitment === null) {
    return (
      <EmptyState
        title="Not available to your role"
        hint="The commercial and legal record of a unit belongs to Sales, Legal and Collections."
      />
    );
  }

  if (commitment.reservation === null && commitment.sale === null) {
    if (["reserved", "contract_pending", "contracted"].includes(commercialStatus)) {
      return (
        <EmptyState
          title="Not visible to you"
          hint="This unit is committed, but the reservation or contract on it belongs to another advisor's buyer."
        />
      );
    }
    return (
      <EmptyState
        title="No active commercial commitment"
        hint="Nothing is reserved or contracted on this unit. A reservation is opened from the project's Sales section."
      />
    );
  }

  const sale = commitment.sale;

  return (
    <>
      {commitment.reservation ? (
        <section>
          <SectionHeader
            title="Reservation"
            actions={
              <Badge tone={reservationTone(commitment.reservation.status)}>
                {reservationLabel(commitment.reservation.status)}
              </Badge>
            }
          />
          <KeyValueGrid columns={3}>
            <KeyValue label="Number" mono value={commitment.reservation.reservation_number} />
            <KeyValue label="Expires" mono value={businessDate(commitment.reservation.expires_on)} />
            <KeyValue
              label="Deposit"
              value={
                <Badge tone={gateTone(commitment.reservation.deposit_gate_status)}>
                  {gateLabel(commitment.reservation.deposit_gate_status)}
                </Badge>
              }
            />
            <KeyValue
              label="Quoted price (ex tax)"
              mono
              value={money(
                commitment.reservation.net_contract_price_ex_tax,
                currencyCodeOf(commitment.reservation.currency_id),
              )}
            />
            <KeyValue
              label="Price locked until"
              mono
              value={businessDate(commitment.reservation.price_locked_until)}
            />
          </KeyValueGrid>
        </section>
      ) : null}

      {sale ? (
        <>
          <section>
            <SectionHeader
              title="Sale contract"
              actions={<Badge tone={saleTone(sale.sale.status)}>{saleLabel(sale.sale.status)}</Badge>}
            />
            <KeyValueGrid columns={3}>
              <KeyValue label="Number" mono value={sale.sale.sale_number} />
              <KeyValue label="SPA number" mono value={sale.sale.spa_number} />
              <KeyValue
                label="Contract price"
                mono
                value={money(sale.sale.total_contract_price, currencyCodeOf(sale.sale.currency_id))}
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
                label="Handover"
                value={
                  sale.handover ? (
                    <Badge tone={handoverTone(sale.handover.handover.status)}>
                      {handoverLabel(sale.handover.handover.status)}
                    </Badge>
                  ) : (
                    "Not opened"
                  )
                }
              />
            </KeyValueGrid>
          </section>

          <section>
            <SectionHeader title="Payment plan" description="Scheduled, not collected." />
            <PlanSummary projectId={projectId} saleId={sale.sale.id} compact />
          </section>

          <section>
            <SectionHeader title="Buyer parties on the contract" />
            <TableScroll label="Contract parties" compact>
              <thead>
                <tr>
                  <th scope="col">Name as identification</th>
                  <th scope="col" className="num">
                    Share
                  </th>
                  <th scope="col">Identity document</th>
                </tr>
              </thead>
              <tbody>
                {sale.parties.map((party) => (
                  <tr key={party.id}>
                    <th scope="row">{party.name_as_identification}</th>
                    <td className="num">{party.share_fraction}</td>
                    <td className="mono">
                      {"identity_document_number" in party ? (
                        `${party.identity_document_type ?? "—"} ${party.identity_document_number ?? ""}`
                      ) : (
                        <span className="subtle">Not shown to your role</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </TableScroll>
          </section>

          <section>
            <SectionHeader title="Legal timeline" />
            {sale.legal.events.length === 0 ? (
              <p className="subtle">Nothing recorded yet.</p>
            ) : (
              <Timeline>
                {sale.legal.events.map((event) => {
                  const stands = sale.legal.effective_event_ids.includes(event.id);
                  return (
                    <TimelineItem
                      key={event.id}
                      title={legalEventLabel(event.event_type)}
                      date={businessDate(event.event_date)}
                      state={stands ? "done" : "void"}
                      aside={
                        stands ? null : (
                          <Badge tone="muted">
                            {event.reverses_event_id ? "Withdrawal" : "Superseded"}
                          </Badge>
                        )
                      }
                    />
                  );
                })}
              </Timeline>
            )}
          </section>

          {sale.cancellation ? (
            <Notice tone="warning">
              A cancellation is running on this contract: {sale.cancellation.reason}
            </Notice>
          ) : null}
        </>
      ) : null}
    </>
  );
}
