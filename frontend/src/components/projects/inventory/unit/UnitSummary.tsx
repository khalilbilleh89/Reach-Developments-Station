"use client";

import type { Reservation, SaleDetail, Unit, UnitPricing } from "@/lib/api";
import {
  Badge,
  Button,
  EmptyState,
  KeyValue,
  KeyValueGrid,
  Notice,
  SectionHeader,
  Stat,
  StatRow,
} from "@/components/ui";
import { useCurrencyCode } from "@/lib/currency";
import { businessDate, money } from "@/lib/format";
import { statusLabel, statusTone } from "@/components/projects/inventory/statusLabels";
import { UnitCollections } from "@/components/projects/collections/UnitCollections";
import { UnitEconomicsSection } from "@/components/projects/economics/UnitEconomicsSection";
import {
  gateLabel,
  gateTone,
  reservationLabel,
  reservationTone,
  saleLabel,
  saleTone,
} from "@/components/projects/sales/labels";

const DIMENSIONS: { key: keyof Unit; label: string }[] = [
  { key: "commercial_status", label: "Commercial" },
  { key: "legal_status", label: "Legal" },
  { key: "collection_status", label: "Collection" },
  { key: "delivery_status", label: "Delivery" },
];

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
 */
export function UnitSummary({
  unit,
  unitPricing,
  commitment,
  onOpenTab,
}: {
  unit: Unit;
  unitPricing: UnitPricing | null;
  commitment: { reservation: Reservation | null; sale: SaleDetail | null } | null;
  onOpenTab: (tab: string) => void;
}) {
  const blocked = unit.release_blockers.length > 0;
  const currencyCodeOf = useCurrencyCode();
  const priceCode = currencyCodeOf(unitPricing?.active_price?.currency_id);

  return (
    <>
      <section>
        <SectionHeader title="Standing" />
        <div className="status-grid">
          {DIMENSIONS.map((dimension) => {
            const value = String(unit[dimension.key]);
            return (
              <div className="status-cell" key={dimension.key}>
                <p className="status-cell-label">{dimension.label}</p>
                <Badge tone={statusTone(value)}>{statusLabel(value)}</Badge>
              </div>
            );
          })}
        </div>
      </section>

      <section>
        <SectionHeader
          title="Release readiness"
          actions={<Button small onClick={() => onOpenTab("release")}>Release controls</Button>}
        />
        <StatRow>
          <Stat
            label="Data completeness"
            value={`${unit.completeness_percent}%`}
            note={unit.is_complete ? "Complete" : "Incomplete"}
            small
          />
          <Stat label="Drawings" value={unit.drawings_approved ? "Approved" : "Not approved"} small />
          <Stat
            label="Legally saleable"
            value={unit.legal_sale_eligible ? "Yes" : "No"}
            small
          />
          <Stat
            label="Pricing"
            value={unit.pricing_approved ? "Approved" : "Not approved"}
            small
          />
          <Stat label="Release date" value={businessDate(unit.release_date)} small />
        </StatRow>
        {blocked ? (
          <Notice tone="warning">
            Not releasable yet: {unit.release_blockers.join("; ")}.
          </Notice>
        ) : (
          <p className="footnote">Nothing recorded is standing in the way of release.</p>
        )}
        {unit.missing_requirements.length > 0 ? (
          <p className="footnote">Outstanding: {unit.missing_requirements.join(", ")}.</p>
        ) : null}
      </section>

      <UnitCollections
        projectId={unit.project_id}
        saleId={commitment?.sale?.sale?.id ?? null}
      />

      <UnitEconomicsSection projectId={unit.project_id} unitId={unit.id} />

      <section>
        <SectionHeader
          title="Price"
          actions={
            unitPricing ? (
              <Button small onClick={() => onOpenTab("pricing")}>
                Price breakdown
              </Button>
            ) : undefined
          }
        />
        {unitPricing === null ? (
          <p className="subtle">Pricing is not available to your role.</p>
        ) : unitPricing.repricing_required ? (
          <Notice tone="error">
            Repricing required. This unit has changed since its list price was set, so the price
            below is what it was offered at and no longer describes it.
          </Notice>
        ) : null}
        {unitPricing?.active_price ? (
          <StatRow>
            <Stat
              label="List price (ex tax)"
              value={money(unitPricing.active_price.reference_price_ex_tax, priceCode)}
            />
            <Stat
              label="Per internal unit"
              value={money(unitPricing.active_price.price_per_internal_area, priceCode)}
              small
            />
            <Stat
              label="Version"
              value={`v${unitPricing.active_price.version_number}`}
              note={`Live from ${businessDate(unitPricing.active_price.valid_from)}`}
              small
            />
          </StatRow>
        ) : unitPricing ? (
          <EmptyState
            title="Not priced"
            hint={
              unitPricing.has_active_configuration
                ? "Generate a price from the project's Pricing section, then have it approved and activated."
                : "This project has no active pricing configuration yet, so no unit can be priced."
            }
          />
        ) : null}
      </section>

      <section>
        <SectionHeader
          title="Commitment"
          actions={
            commitment && (commitment.reservation || commitment.sale) ? (
              <Button small onClick={() => onOpenTab("commercial")}>
                Sale and legal
              </Button>
            ) : undefined
          }
        />
        {commitment === null ? (
          <p className="subtle">Not available to your role.</p>
        ) : commitment.reservation === null && commitment.sale === null ? (
          <p className="subtle">No active commercial commitment on this unit.</p>
        ) : (
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
                      <Badge tone={saleTone(commitment.sale.sale.status)}>
                        {saleLabel(commitment.sale.sale.status)}
                      </Badge>
                    </>
                  }
                />
                <KeyValue label="SPA number" mono value={commitment.sale.sale.spa_number} />
                <KeyValue
                  label="Contract price"
                  mono
                  value={money(
                    commitment.sale.sale.total_contract_price,
                    currencyCodeOf(commitment.sale.sale.currency_id),
                  )}
                />
              </>
            ) : null}
          </KeyValueGrid>
        )}
      </section>
    </>
  );
}
