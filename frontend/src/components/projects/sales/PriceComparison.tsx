"use client";

import type { SalesPriceFacts } from "@/lib/api";
import { KeyValue, KeyValueGrid } from "@/components/ui";
import { useCurrencyCode } from "@/lib/currency";
import { money } from "@/lib/format";

export function varianceDirection(amount: string) {
  return /^-?0(?:\.0+)?$/.test(amount) ? "At list" : amount.startsWith("-") ? "Below list" : "Above list";
}

export function PriceComparison({ facts }: { facts: SalesPriceFacts }) {
  const codeOf = useCurrencyCode();
  const direction = varianceDirection(facts.price_variance_amount);
  const sign = direction === "Above list" ? "+" : "";
  return <KeyValueGrid columns={2}>
    <KeyValue label="Inventory list price at deal · ex tax" value={money(facts.reference_price_ex_tax, codeOf(facts.currency_id))} />
    <KeyValue label="Agreed sales price · ex tax" value={money(facts.sales_price_ex_tax, codeOf(facts.currency_id))} />
    <KeyValue label={`Difference · ${direction}`} value={`${sign}${money(facts.price_variance_amount, codeOf(facts.currency_id))}`} />
    <KeyValue label="Difference %" value={facts.price_variance_fraction === null ? "Unavailable — list price is zero" : facts.price_variance_percentage} />
  </KeyValueGrid>;
}
