"use client";

import type { PriceComponent, PriceVersionDetail } from "@/lib/api";
import { Badge, EmptyState } from "@/components/ui";

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

function Amount({ value }: { value: string | null }) {
  if (value === null) return <>—</>;
  return <span className="mono nowrap">{value}</span>;
}

function overridden(component: PriceComponent): boolean {
  return component.override_amount !== null;
}

export function PriceWaterfall({ version }: { version: PriceVersionDetail }) {
  if (version.components.length === 0) {
    return <EmptyState title="No components" hint="This price has no lines to show." />;
  }

  return (
    <>
      <div className="table-scroll">
        <table className="table">
          <caption className="visually-hidden">Price components</caption>
          <thead>
            <tr>
              <th scope="col">#</th>
              <th scope="col">Source</th>
              <th scope="col">Line</th>
              <th scope="col">Quantity</th>
              <th scope="col">Rate</th>
              <th scope="col">Factor</th>
              <th scope="col">Basis</th>
              <th scope="col">Calculated</th>
              <th scope="col">Override</th>
              <th scope="col">Final</th>
            </tr>
          </thead>
          <tbody>
            {version.components.map((component) => (
              <tr key={component.id}>
                <td>{component.sequence}</td>
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
                <td className="mono nowrap">
                  {component.quantity === null
                    ? "—"
                    : `${component.quantity}${
                        component.unit_of_measure ? ` ${component.unit_of_measure}` : ""
                      }`}
                </td>
                <td>
                  <Amount value={component.rate} />
                </td>
                <td className="mono nowrap">{component.factor ?? "—"}</td>
                <td>
                  <Amount value={component.basis_amount} />
                </td>
                <td>
                  <Amount value={component.calculated_amount} />
                </td>
                <td>
                  <Amount value={component.override_amount} />
                </td>
                <td>
                  <Amount value={component.final_amount} />
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <th scope="row" colSpan={9}>
                Approved reference price (ex tax)
              </th>
              <td className="mono nowrap">{version.reference_price_ex_tax}</td>
            </tr>
          </tfoot>
        </table>
      </div>
      {version.components.some(overridden) ? (
        <dl className="reference-list">
          {version.components.filter(overridden).map((component) => (
            <div key={`reason-${component.id}`}>
              <dt className="reference-term">{component.label}</dt>
              <dd className="reference-value">{component.override_reason}</dd>
            </div>
          ))}
        </dl>
      ) : null}
    </>
  );
}
