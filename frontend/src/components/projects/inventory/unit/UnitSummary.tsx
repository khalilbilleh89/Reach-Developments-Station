"use client";

import type { CollectionSaleSummary, Unit, UnitPricing } from "@/lib/api";
import type { Answer } from "@/lib/answer";
import {
  Badge,
  Button,
  Disclosure,
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

/**
 * The first screen of Unit 360: where this unit stands, in one view.
 *
 * The four status dimensions are shown side by side and never merged. "Sold" is
 * not one fact in this product — a unit can be contracted, unpaid, unregistered
 * and undelivered at the same time, and three different teams need to see their
 * own answer without reading somebody else's as theirs.
 *
 * Nothing here is computed. Every status, blocker, gate and figure came back
 * from the API on this request; the browser decides only how to arrange them.
 * Every module here is one answer, made once by the unit file for the header
 * and the sections alike — one request each, only for a role the server
 * answers — so the overview and the section can never disagree. A module that
 * was refused says so, one that failed says so, and neither is drawn as a
 * unit with no price or no commitment.
 */
export function UnitSummary({
  unit,
  pricing,
  commitment,
  collection,
  onOpenTab,
}: {
  unit: Unit;
  pricing: Answer<UnitPricing>;
  commitment: Answer<Commitment>;
  collection: Answer<CollectionSaleSummary>;
  onOpenTab: (tab: string) => void;
}) {
  const blocked = unit.release_blockers.length > 0;

  return (
    <div className="record-overview">
      <section className="record-section record-standing">
        <SectionHeader title="Property profile" actions={<Button small onClick={() => onOpenTab("detail")}>Physical record</Button>} />
        <KeyValueGrid columns={3}>
          <KeyValue label="Property" value={[unit.unit_type_code, unit.bedrooms === null ? null : `${unit.bedrooms} bedrooms`, unit.bathrooms === null ? null : `${unit.bathrooms} bathrooms`].filter(Boolean).join(" · ") || unit.asset_class} />
          <KeyValue label="Location" value={[unit.phase_code, unit.building_code, unit.floor_code].filter(Boolean).join(" → ") || "Not recorded"} />
          {unit.view_class_code || unit.orientation_code ? <KeyValue label="View / orientation" value={[unit.view_class_code, unit.orientation_code].filter(Boolean).join(" · ")} /> : null}
          <KeyValue label="Parking / storage" value={`${unit.parking_count} parking · ${unit.storage_count} storage`} />
          <KeyValue label="Area revision" value={unit.area_revision_code ?? "Not recorded"} />
          <KeyValue label="Delivery" value={<Button small variant="quiet" onClick={() => onOpenTab("construction")}>Inspect construction stages</Button>} />
        </KeyValueGrid>
        <p className="footnote">Parking and storage remain separate attached assets, excluded from gross area.</p>
      </section>
      {collection.status === "off" ? null : (
        <section className="record-section unit-account">
          <SectionHeader
            title="Collections"
            actions={
              collection.status === "ready" ? (
                <Button small onClick={() => onOpenTab("collections")}>
                  Account position
                </Button>
              ) : undefined
            }
          />
          <CollectionSnapshot answer={collection} />
        </section>
      )}

      {pricing.status === "off" ? null : (
        <section className="record-section">
          <SectionHeader
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

      {commitment.status === "off" ? null : (
        <section className="record-section">
          <SectionHeader
            title="Commitment"
            actions={
              commitment.status === "ready" ? (
                <Button small onClick={() => onOpenTab("commercial")}>
                  Sale and legal
                </Button>
              ) : undefined
            }
          />
          <CommitmentSnapshot answer={commitment} commercialStatus={unit.commercial_status} />
        </section>
      )}
      <Disclosure title="Release readiness" context="Configuration · approvals · release controls">
        <Button small onClick={() => onOpenTab("release")}>Release controls</Button>
        <MetricGroup compact>
          <Metric
            label="Data completeness"
            value={`${unit.completeness_percent}%`}
            note={unit.is_complete ? "Complete" : "Incomplete"}
            size="sm"
          />
          <Metric label="Drawings" value={unit.drawings_approved ? "Approved" : "Not approved"} size="sm" />
          <Metric label="Legally saleable" value={unit.legal_sale_eligible ? "Yes" : "No"} size="sm" />
          <Metric label="Pricing" value={unit.pricing_approved ? "Approved" : "Not approved"} size="sm" />
          <Metric label="Release date" value={businessDate(unit.release_date)} size="sm" />
        </MetricGroup>
        {blocked ? (
          <Notice tone="warning">Not releasable yet: {unit.release_blockers.join("; ")}.</Notice>
        ) : (
          <p className="footnote">Nothing recorded is standing in the way of release.</p>
        )}
        {unit.missing_requirements.length > 0 ? (
          <p className="footnote">Outstanding: {unit.missing_requirements.join(", ")}.</p>
        ) : null}
      </Disclosure>

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
function CommitmentSnapshot({ answer, commercialStatus }: { answer: Answer<Commitment>; commercialStatus: string }) {
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
function CollectionSnapshot({ answer }: { answer: Answer<CollectionSaleSummary> }) {
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
