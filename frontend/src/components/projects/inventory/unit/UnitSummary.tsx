"use client";

import type { CollectionSaleSummary, Unit, UnitPricing } from "@/lib/api";
import type { Answer } from "@/lib/answer";
import {
  Badge,
  Button,
  EmptyState,
  KeyValue,
  KeyValueGrid,
  Loading,
  Metric,
  MetricGroup,
  Notice,
  Position,
  PositionFigure,
  SectionHeader,
} from "@/components/ui";
import { useCurrencyCode } from "@/lib/currency";
import { businessDate, money } from "@/lib/format";
import type { Commitment } from "@/components/projects/inventory/unit/UnitCommitment";
import { unitCollectionLabel, unitCollectionTone } from "@/components/projects/collections/labels";
import {
  gateLabel,
  gateTone,
  reservationLabel,
  reservationTone,
  saleLabel,
  saleTone,
} from "@/components/projects/sales/labels";

/** The commercial states in which a reservation or contract owns the unit. */
const COMMITTED = new Set(["reserved", "contract_pending", "contracted"]);

/** Inventory profile and launch price; transaction snapshots below serve Sales. */
export function UnitSummary({
  unit,
  pricing,
  onOpenTab,
}: {
  unit: Unit;
  pricing: Answer<UnitPricing>;
  onOpenTab: (tab: string) => void;
}) {

  return (
    <div className="record-overview">
      <section className="record-section record-standing">
        <SectionHeader level={2} title="Property profile" actions={<Button small onClick={() => onOpenTab("detail")}>Physical record</Button>} />
        <KeyValueGrid columns={3}>
          <KeyValue label="Property" value={[unit.asset_class, unit.bedrooms === null ? null : `${unit.bedrooms} bedrooms`, unit.bathrooms === null ? null : `${unit.bathrooms} bathrooms`].filter(Boolean).join(" · ") || unit.asset_class} />
          <KeyValue label="Location" value={[unit.phase_code, unit.building_code, unit.floor_code].filter(Boolean).join(" → ") || "Not recorded"} />
          {unit.view_class_code || unit.orientation_code ? <KeyValue label="View / orientation" value={[unit.view_class_code, unit.orientation_code].filter(Boolean).join(" · ")} /> : null}
          <KeyValue label="Parking / storage" value={`${unit.parking_count} parking · ${unit.storage_count} storage`} />
          <KeyValue label="Area revision" value={unit.area_revision_code ?? "Not recorded"} />
        </KeyValueGrid>
        <p className="footnote">Parking and storage remain separate attached assets, excluded from gross area.</p>
      </section>
      {pricing.status === "off" ? null : (
        <section className="record-section">
          <SectionHeader level={2}
            title="Price"
            actions={
              pricing.status === "ready" ? (
                <Button small onClick={() => onOpenTab("pricing")}>
                  Price breakdown
                </Button>
              ) : undefined
            }
          />
          <PriceSnapshot answer={pricing} />
        </section>
      )}

      <section className="record-section">
        <SectionHeader level={2} title="Launch preparation" actions={<Button small onClick={() => onOpenTab("release")}>Release</Button>} />
        <KeyValueGrid columns={3}>
          <KeyValue label="Drawings" value={unit.drawings_approved ? "Approved" : "Not approved"} />
          <KeyValue label="Launch price" value={unit.pricing_approved ? "Approved" : "Not approved"} />
          <KeyValue label="Release date" value={businessDate(unit.release_date)} />
          <KeyValue label="Release batch" value={unit.release_batch} />
        </KeyValueGrid>
      </section>

    </div>
  );
}

/** The live list price, or the reason there is none to show. */
function PriceSnapshot({ answer }: { answer: Answer<UnitPricing> }) {
  const currencyCodeOf = useCurrencyCode();
  if (answer.status === "loading") return <Loading label="Loading the unit's pricing" shape="metrics" />;
  if (answer.status === "denied") return <p className="subtle">Pricing is not available to your role.</p>;
  if (answer.status === "failed") {
    return (
      <Notice tone="error">
        Pricing could not be loaded. {answer.message} The list price is not known until it can be.
      </Notice>
    );
  }
  if (answer.status !== "ready") return null;

  const unitPricing = answer.data;
  const price = unitPricing.active_price;
  const priceCode = currencyCodeOf(price?.currency_id);
  return (
    <>
      {unitPricing.repricing_required ? (
        <Notice tone="error">
          Repricing required. This unit has changed since its list price was set, so the price
          below is what it was offered at and no longer describes it.
        </Notice>
      ) : null}
      {price ? (
        <Position compact>
          <PositionFigure lead label="List price (ex tax)" value={money(price.reference_price_ex_tax, priceCode)} />
          <PositionFigure label={`Per gross ${unitPricing.gross_area_unit ?? "area unit"}`} value={money(unitPricing.price_per_gross_area, priceCode)} note={unitPricing.price_per_gross_area === null ? "Needs complete gross measurements and a current price" : "Ex tax"} />
          <PositionFigure
            label="Version"
            value={`v${price.version_number}`}
            note={`Live from ${businessDate(price.valid_from)}`}

          />
        </Position>
      ) : (
        <EmptyState
          compact
          title="Not priced"
          hint={
            unitPricing.has_active_configuration
              ? "Enter a selling price in this unit’s Pricing tab, then have it approved and activated."
              : "A pricing writer can enter a selling price directly in this unit’s Pricing tab."
          }
        />
      )}
    </>
  );
}

/**
 * The reservation or contract on the unit, or the reason none is shown.
 *
 * A successful read with nothing in it is a fact of its own: no commitment,
 * or — where the unit's own status says it is committed — a commitment that
 * belongs to another advisor's buyer and is withheld from this reader. A
 * failed read is neither, and is said as a failure.
 */
export function CommitmentSnapshot({ answer, commercialStatus }: { answer: Answer<Commitment>; commercialStatus: string }) {
  const currencyCodeOf = useCurrencyCode();
  if (answer.status === "loading") return <Loading label="Loading the commercial record" shape="rows" rows={2} />;
  if (answer.status === "denied") return <p className="subtle">Not available to your role.</p>;
  if (answer.status === "failed") {
    return (
      <Notice tone="error">
        The commercial record could not be loaded. {answer.message} Whether this unit is reserved or
        contracted is not known until it can be.
      </Notice>
    );
  }
  if (answer.status !== "ready") return null;

  const commitment = answer.data;
  if (commitment.reservation === null && commitment.sale === null) {
    return (
      <p className="subtle">
        {COMMITTED.has(commercialStatus)
          ? "This unit is committed, but the reservation or contract on it belongs to another advisor's buyer and is not visible to you."
          : "No active commercial commitment on this unit."}
      </p>
    );
  }
  return (
    <KeyValueGrid columns={3}>
      {commitment.reservation ? (
        <>
          <KeyValue
            label="Reservation"
            value={
              <>
                <span className="mono">{commitment.reservation.reservation_number}</span>{" "}
                <Badge tone={reservationTone(commitment.reservation.status)}>
                  {reservationLabel(commitment.reservation.status)}
                </Badge>
              </>
            }
          />
          <KeyValue label="Expires" mono value={businessDate(commitment.reservation.expires_on)} />
          <KeyValue
            label="Deposit"
            value={
              <Badge tone={gateTone(commitment.reservation.deposit_gate_status)}>
                {gateLabel(commitment.reservation.deposit_gate_status)}
              </Badge>
            }
          />
        </>
      ) : null}
      {commitment.sale ? (
        <>
          <KeyValue
            label="Contract"
            value={
              <>
                <span className="mono">{commitment.sale.sale.sale_number}</span>{" "}
                <Badge tone={saleTone(commitment.sale.sale.status)}>{saleLabel(commitment.sale.sale.status)}</Badge>
              </>
            }
          />
          <KeyValue label="SPA number" mono value={commitment.sale.sale.spa_number} />
          <KeyValue
            label="Contract total · incl tax"
            mono
            value={money(commitment.sale.sale.total_contract_price, currencyCodeOf(commitment.sale.sale.currency_id))}
          />
        </>
      ) : null}
    </KeyValueGrid>
  );
}

/** The cash position behind the collection status, from the account's own summary. */
export function CollectionSnapshot({ answer }: { answer: Answer<CollectionSaleSummary> }) {
  const currencyCodeOf = useCurrencyCode();
  if (answer.status === "loading") return <Loading label="Loading the collections position" shape="metrics" />;
  if (answer.status === "denied") return <p className="subtle">Not available to your role.</p>;
  if (answer.status === "failed") {
    return (
      <Notice tone="error">
        The collections position could not be loaded. {answer.message} No balance is known until it
        can be.
      </Notice>
    );
  }
  if (answer.status !== "ready") return null;

  const summary = answer.data;
  const code = currencyCodeOf(summary.currency_id);
  return (
    <MetricGroup compact>
      <Metric
        label="Position"
        value={
          <Badge tone={unitCollectionTone(summary.derived_collection_status)}>
            {unitCollectionLabel(summary.derived_collection_status)}
          </Badge>
        }
        size="sm"
      />
      <Metric label="Collected" value={money(summary.allocated_total, code)} note="Confirmed and applied" size="sm" />
      <Metric label="Outstanding" value={money(summary.outstanding_total, code)} size="sm" />
      <Metric
        label="Overdue"
        value={money(summary.overdue_total, code)}
        tone={summary.oldest_overdue_days > 0 ? "danger" : "neutral"}
        note={summary.oldest_overdue_days > 0 ? `Oldest ${summary.oldest_overdue_days} days` : "Nothing past grace"}
        size="sm"
      />
    </MetricGroup>
  );
}
