"use client";

import { useState } from "react";

import type { PriceComponent, PriceVersionDetail } from "@/lib/api";
import {
  Badge,
  Button,
  EmptyState,
  KeyValue,
  KeyValueGrid,
  TableScroll,
  Waterfall,
  WaterfallRow,
} from "@/components/ui";
import { useCurrencyCode } from "@/lib/currency";
import { money } from "@/lib/format";

/**
 * The lines a price is made of, in the order they were applied.
 *
 * A total on its own is the spreadsheet cell this product exists to replace, so
 * every line shows what it read, what rate or factor it applied, what the rules
 * produced and — where somebody overrode it — what they decided instead. Nothing
 * here calculates: the amounts are the backend's, and the browser formats them.
 *
 * The composition reads top to bottom to the reference price. The arithmetic
 * behind each line — quantity, rate, factor, basis, calculated and override —
 * is one click away rather than ten columns wide, because a Finance reviewer
 * wants it and a Sales advisor only wants to know what the number is.
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

function overridden(component: PriceComponent): boolean {
  return component.override_amount !== null;
}

/**
 * What a line applied, in words: "12 m² × 1.0 @ 1,250.00".
 *
 * The Rate stays undecorated — a rate is money PER AREA, and labelling it as
 * a plain currency amount would misstate what it is. A factor is a multiplier.
 */
function basisOf(component: PriceComponent): string {
  const parts: string[] = [TYPE_LABELS[component.component_type] ?? component.component_type];
  if (component.quantity !== null) {
    parts.push(`${component.quantity}${component.unit_of_measure ? ` ${component.unit_of_measure}` : ""}`);
  }
  if (component.rate !== null) parts.push(`@ ${money(component.rate)}`);
  if (component.factor !== null) parts.push(`× ${component.factor}`);
  return parts.join(" · ");
}

export function PriceWaterfall({ version }: { version: PriceVersionDetail }) {
  const currencyCodeOf = useCurrencyCode();
  const [arithmetic, setArithmetic] = useState(false);
  const code = currencyCodeOf(version.currency_id);
  if (version.components.length === 0) {
    return <EmptyState compact title="No components" hint="This price has no lines to show." />;
  }
  const overrides = version.components.filter(overridden);

  return (
    <>
      <Waterfall>
        {version.components.map((component) => (
          <WaterfallRow
            key={component.id}
            label={
              <>
                {component.label}
                {overridden(component) ? (
                  <>
                    {" "}
                    <Badge tone="muted">Overridden</Badge>
                  </>
                ) : null}
              </>
            }
            note={basisOf(component)}
            amount={money(component.final_amount, code)}
          />
        ))}
        <WaterfallRow
          label="Approved reference price (ex tax)"
          amount={money(version.reference_price_ex_tax, code)}
          kind="total"
        />
      </Waterfall>

      <p className="footnote">
        <Button small variant="quiet" onClick={() => setArithmetic((open) => !open)}>
          {arithmetic ? "Hide the arithmetic" : "Show the arithmetic"}
        </Button>
      </p>

      {arithmetic ? (
        <TableScroll label="Price components" compact>
          <thead>
            <tr>
              <th scope="col" className="num">
                #
              </th>
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
                <th scope="row">{component.label}</th>
                <td className="num">
                  {component.quantity === null
                    ? "—"
                    : `${component.quantity}${component.unit_of_measure ? ` ${component.unit_of_measure}` : ""}`}
                </td>
                <td className="num">{money(component.rate)}</td>
                <td className="num">{component.factor ?? "—"}</td>
                <td className="num">{money(component.basis_amount, code)}</td>
                <td className="num">{money(component.calculated_amount, code)}</td>
                <td className="num">{money(component.override_amount, code)}</td>
                <td className="num">{money(component.final_amount, code)}</td>
              </tr>
            ))}
          </tbody>
        </TableScroll>
      ) : null}

      {overrides.length > 0 ? (
        <>
          <h4 className="section-heading">Why a line was overridden</h4>
          <KeyValueGrid columns={2}>
            {overrides.map((component) => (
              <KeyValue key={`reason-${component.id}`} label={component.label} value={component.override_reason} />
            ))}
          </KeyValueGrid>
        </>
      ) : null}
    </>
  );
}
