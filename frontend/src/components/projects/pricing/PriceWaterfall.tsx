"use client";

import type { PriceComponent, PriceVersionDetail } from "@/lib/api";
import { Badge, EmptyState, KeyValue, KeyValueGrid, TableScroll } from "@/components/ui";
import { useCurrencyCode } from "@/lib/currency";
import { money } from "@/lib/format";

/**
 * The lines a price is made of, in the order they were applied.
 *
 * A total on its own is the spreadsheet cell this product exists to replace, so
 * every line shows what it read, what rate or factor it applied, what the rules
 * produced and — where somebody overrode it — what they decided instead. Nothing
 * here calculates: the amounts are the backend's, and the browser formats them.
 */
const TYPE_LABELS: Record<string, string> = {
  base_internal: "Internal area",
  base_attached: "Attached area",
  scope_adjustment: "Scope adjustment",
  feature_premium: "Feature premium",
  sub_asset_premium: "Parking / storage",
  escalation: "Escalation",
  paid_upgrade: "Paid upgrade",
  premium_cap_adjustment: "Premium cap",
  manual_override: "Override",
};

/**
 * A money cell: grouped, denominated in the version's own currency.
 *
 * The Rate and Factor columns stay undecorated — a rate is money PER AREA and
 * a factor is a multiplier, and labelling either as a plain currency amount
 * would misstate what it is.
 */
function Amount({ value, code }: { value: string | null; code: string | null }) {
  return <>{money(value, code)}</>;
}

function overridden(component: PriceComponent): boolean {
  return component.override_amount !== null;
}

export function PriceWaterfall({ version }: { version: PriceVersionDetail }) {
  const currencyCodeOf = useCurrencyCode();
  const code = currencyCodeOf(version.currency_id);
  if (version.components.length === 0) {
    return <EmptyState title="No components" hint="This price has no lines to show." />;
  }

  return (
    <>
      <TableScroll label="Price components">
          <thead>
            <tr>
              <th scope="col" className="num">
                #
              </th>
              <th scope="col">Source</th>
              <th scope="col">Line</th>
              <th scope="col" className="num">
                Quantity
              </th>
              <th scope="col" className="num">
                Rate
              </th>
              <th scope="col" className="num">
                Factor
              </th>
              <th scope="col" className="num">
                Basis
              </th>
              <th scope="col" className="num">
                Calculated
              </th>
              <th scope="col" className="num">
                Override
              </th>
              <th scope="col" className="num">
                Final
              </th>
            </tr>
          </thead>
          <tbody>
            {version.components.map((component) => (
              <tr key={component.id}>
                <td className="num">{component.sequence}</td>
                <td>{TYPE_LABELS[component.component_type] ?? component.component_type}</td>
                <th scope="row">
                  {component.label}
                  {overridden(component) ? (
                    <>
                      {" "}
                      <Badge tone="muted">Overridden</Badge>
                    </>
                  ) : null}
                </th>
                <td className="num">
                  {component.quantity === null
                    ? "—"
                    : `${component.quantity}${
                        component.unit_of_measure ? ` ${component.unit_of_measure}` : ""
                      }`}
                </td>
                <td className="num">{money(component.rate)}</td>
                <td className="num">{component.factor ?? "—"}</td>
                <td className="num">
                  <Amount value={component.basis_amount} code={code} />
                </td>
                <td className="num">
                  <Amount value={component.calculated_amount} code={code} />
                </td>
                <td className="num">
                  <Amount value={component.override_amount} code={code} />
                </td>
                <td className="num">
                  <Amount value={component.final_amount} code={code} />
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <th scope="row" colSpan={9}>
                Approved reference price (ex tax)
              </th>
              <td className="num">{money(version.reference_price_ex_tax, code)}</td>
            </tr>
          </tfoot>
      </TableScroll>
      {version.components.some(overridden) ? (
        <>
          <h4 className="section-heading">Why a line was overridden</h4>
          <KeyValueGrid columns={2}>
            {version.components.filter(overridden).map((component) => (
              <KeyValue
                key={`reason-${component.id}`}
                label={component.label}
                value={component.override_reason}
              />
            ))}
          </KeyValueGrid>
        </>
      ) : null}
    </>
  );
}
