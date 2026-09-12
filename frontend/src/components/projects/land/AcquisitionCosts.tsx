"use client";

import type { LandParcel } from "@/lib/api";
import { money, percent } from "@/lib/format";
import { KeyValue, KeyValueGrid } from "@/components/ui";

export function AcquisitionCosts({ parcel }: { parcel: LandParcel }) {
  const price = (value: string | null) => value === null ? "Not recorded" : money(value, parcel.base_currency_code);
  return <>
    <KeyValueGrid columns={2}>
      <KeyValue label="Taxes" value={price(parcel.acquisition_tax_amount)} />
      <KeyValue label="Tax rate on purchase price" value={percent(parcel.acquisition_tax_rate_fraction)} />
      <KeyValue label="Agent fee" value={price(parcel.agent_fee_amount)} />
      <KeyValue label="Agent fee / purchase price" value={percent(parcel.agent_fee_rate_fraction)} />
      <KeyValue label="Legal fee" value={price(parcel.legal_fee_amount)} />
      <KeyValue label="Legal fee / purchase price" value={percent(parcel.legal_fee_rate_fraction)} />
      <KeyValue label="Registration fee" value={price(parcel.registration_fee_amount)} />
      <KeyValue label="Registration fee / purchase price" value={percent(parcel.registration_fee_rate_fraction)} />
      <KeyValue label="Total acquisition fees (including taxes)" value={price(parcel.total_acquisition_fees)} />
    </KeyValueGrid>
    <p className="footnote">Taxes = purchase price × tax %. Total acquisition cost = purchase price + taxes + other fees + agent + legal + registration. Do not repeat itemized charges in other fees.</p>
  </>;
}
