"use client";

import type { LandParcel } from "@/lib/api";
import { money, percent } from "@/lib/format";
import { Disclosure, KeyValue, KeyValueGrid } from "@/components/ui";

export function AcquisitionCosts({ parcel }: { parcel: LandParcel }) {
  const price = (value: string | null) => value === null ? "Not recorded" : money(value, parcel.base_currency_code);
  return <>
    <dl className="land-cost-breakdown">
      {([
        ["Taxes", parcel.acquisition_tax_amount], ["Agent fee", parcel.agent_fee_amount],
        ["Legal fee", parcel.legal_fee_amount], ["Registration fee", parcel.registration_fee_amount],
        ["Total fees, including taxes", parcel.total_acquisition_fees],
      ] as const).map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{price(value)}</dd></div>)}
    </dl>
    <Disclosure title="Fee rates & calculation basis">
      <KeyValueGrid columns={2}>
        <KeyValue label="Tax rate on purchase price" value={percent(parcel.acquisition_tax_rate_fraction)} />
        <KeyValue label="Agent fee / purchase price" value={percent(parcel.agent_fee_rate_fraction)} />
        <KeyValue label="Legal fee / purchase price" value={percent(parcel.legal_fee_rate_fraction)} />
        <KeyValue label="Registration fee / purchase price" value={percent(parcel.registration_fee_rate_fraction)} />
      </KeyValueGrid>
      <p className="footnote">Taxes = purchase price × tax %. Total acquisition cost = purchase price + taxes + other fees + agent + legal + registration. Do not repeat itemized charges in other fees.</p>
    </Disclosure>
  </>;
}
