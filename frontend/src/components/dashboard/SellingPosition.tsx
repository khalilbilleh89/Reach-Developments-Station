"use client";

import type { ProjectSection } from "@/components/shell/navigation";
import type { CollectionProjectSummary, SalesRegisterTotals, UnitRegister } from "@/lib/api";
import { Button } from "@/components/ui";
import { money } from "@/lib/format";

/** One band of the stock bar: a commercial state and how much of the building it holds. */
interface Band {
  key: string;
  label: string;
  count: number;
}

/**
 * Am I selling?
 *
 * The page's first answer, and the reason an owner opens it. Everything here
 * is a figure the overview already asked for: the unit register's own counts,
 * the sales register's contracted value, and the collections strip. Nothing is
 * derived, weighted or estimated in the browser — a number a director cannot
 * reproduce from a module is a number this band does not show.
 *
 * The stock bar is the whole building, once, in lifecycle order: sold, then
 * reserved, then what may still be sold, then what has not been put out. It is
 * proportion, not decoration, so a development that has sold nothing shows one
 * long band of available stock rather than an empty frame — which is the
 * honest picture, and reads as a beginning rather than a fault.
 */
export function SellingPosition({
  units,
  deals,
  cash,
  currencyCode,
  onNavigate,
}: {
  units: UnitRegister | null;
  deals: SalesRegisterTotals | null;
  cash: CollectionProjectSummary | null;
  /** The project's base currency, for the figures sales did not label. */
  currencyCode: string | null;
  onNavigate: (section: ProjectSection) => void;
}) {
  if (!units) return null;

  const bands: Band[] = [
    { key: "sold", label: "Sold", count: units.sold_count },
    { key: "reserved", label: "Reserved", count: units.reserved_count },
    { key: "available", label: "Available", count: units.available_count },
    { key: "held", label: "Held", count: units.held_count },
    { key: "unreleased", label: "Unreleased", count: units.unreleased_count },
  ];
  // The bar describes the register's own total, so a unit in a state this band
  // does not name still takes its share of the width rather than inflating the
  // states that are named.
  const total = units.total || 1;

  // One currency, or none. A development collecting in two currencies has no
  // single "collected" figure, and inventing one by adding them would be the
  // first lie on the page; the strip says so and sends the reader to the
  // module that shows each currency on its own.
  const purses = cash?.currencies ?? [];
  const purse = purses.length === 1 ? purses[0] : null;
  const mixed = purses.length > 1;
  const purseCode = purse ? purse.currency_id : null;

  const contracted = deals?.mixed_currency ? null : (deals?.contracted_value ?? null);

  return (
    <section className="selling-position" aria-label="Commercial position">
      <div className="selling-headline">
        <div className="selling-lead">
          <span className="selling-label">Contracted</span>
          <strong className="selling-figure num">
            {deals?.mixed_currency ? "Several currencies" : money(contracted, currencyCode)}
          </strong>
          <span className="selling-note">
            {units.sold_count === 0
              ? "Nothing contracted yet."
              : `${units.sold_count} of ${units.total} units sold.`}
          </span>
        </div>
        <div className="selling-counts">
          <div className="selling-count">
            <span className="selling-label">Sold</span>
            <strong className="selling-count-figure num">{units.sold_count}</strong>
          </div>
          <div className="selling-count">
            <span className="selling-label">Reserved</span>
            <strong className="selling-count-figure num">{units.reserved_count}</strong>
          </div>
          <div className="selling-count">
            <span className="selling-label">Available</span>
            <strong className="selling-count-figure selling-count-live num">
              {units.available_count}
            </strong>
          </div>
        </div>
      </div>

      <div className="selling-stock">
        <div className="selling-bar" role="img" aria-label={bands.map((band) => `${band.label} ${band.count}`).join(", ")}>
          {bands
            .filter((band) => band.count > 0)
            .map((band) => (
              <span
                key={band.key}
                className={`selling-bar-part selling-bar-${band.key}`}
                style={{ width: `${(band.count / total) * 100}%` }}
              />
            ))}
        </div>
        <ul className="selling-legend">
          {bands.map((band) => (
            <li key={band.key}>
              <span className={`selling-key selling-bar-${band.key}`} />
              {band.label} {band.count}
            </li>
          ))}
        </ul>
      </div>

      <div className="selling-money">
        <div className="selling-money-item">
          <span className="selling-label">Collected</span>
          <strong className="selling-money-figure num">
            {mixed ? "Several currencies" : money(purse?.confirmed_receipts_total ?? null, purseCode)}
          </strong>
        </div>
        <div className="selling-money-item">
          <span className="selling-label">Due</span>
          <strong className="selling-money-figure num">
            {mixed ? "Several currencies" : money(purse?.due_total ?? null, purseCode)}
          </strong>
        </div>
        <div className="selling-money-item">
          <span className="selling-label">Overdue</span>
          <strong className="selling-money-figure selling-money-overdue num">
            {mixed ? "Several currencies" : money(purse?.overdue_total ?? null, purseCode)}
          </strong>
        </div>
        <div className="selling-money-item selling-money-action">
          <Button small variant="quiet" onClick={() => onNavigate("sales")}>
            Open sales
          </Button>
        </div>
      </div>
    </section>
  );
}
