"use client";

import type { LandParcel } from "@/lib/api";
import { businessDate, money, percent } from "@/lib/format";
import { Button, KeyValue, KeyValueGrid, StatusDot } from "@/components/ui";
import { measurement } from "./presentation";

/** A parcel is a property dossier, not a row of nine equally weighted fields. */
export function ParcelCollection({ parcels, canSeeCost, onOpen }: {
  parcels: LandParcel[]; canSeeCost: boolean; onOpen: (parcel: LandParcel) => void;
}) {
  return <div className="parcel-collection" aria-label="Land parcels">
    {parcels.map(parcel => <article className="parcel-estate" key={parcel.id}>
      <div className="parcel-estate-main">
        <header className="parcel-estate-identity">
          <div className="parcel-estate-kicker"><span>Registered land</span><StatusDot tone={parcel.is_active ? "success" : "muted"}>{parcel.is_active ? "Active" : "Inactive"}</StatusDot></div>
          <div className="parcel-estate-title"><div><span className="eyebrow">Parcel</span><h2>{parcel.plot_number}</h2></div><div className="parcel-estate-area"><strong>{measurement(parcel.land_area)}</strong><span>{parcel.area_unit}</span></div></div>
          <p className="parcel-estate-deed">{parcel.title_deed_number ? `Title deed ${parcel.title_deed_number}` : "Title deed not recorded"}</p>
        </header>
        <div className="parcel-estate-facts"><KeyValueGrid columns={2}>
          <KeyValue label="Ownership" value={parcel.ownership_type ?? "Not established"} />
          <KeyValue label="Title status" value={parcel.title_status ?? "Not established"} />
          <KeyValue label="Ownership share" value={parcel.ownership_share_fraction != null ? percent(parcel.ownership_share_fraction) : "Not recorded"} />
          <KeyValue label="Cadastral reference" value={parcel.cadastral_reference ?? "Not recorded"} />
        </KeyValueGrid></div>
        <footer className="parcel-estate-footer"><span>Title, site and supporting records</span><Button variant="primary" onClick={() => onOpen(parcel)}>Open parcel {parcel.plot_number}</Button></footer>
      </div>
      <aside className="parcel-estate-context">
        {canSeeCost && parcel.financials_visible !== false ? <section><span className="eyebrow">Acquisition</span><p className="parcel-estate-price">{money(parcel.purchase_price, parcel.base_currency_code)}</p><p className="footnote">Recorded purchase price · fees separate</p><div className="parcel-estate-date"><span>Acquired</span><strong>{businessDate(parcel.acquisition_date)}</strong></div></section> : <section><span className="eyebrow">Acquisition</span><p>{businessDate(parcel.acquisition_date)}</p></section>}
        <section><span className="eyebrow">Planning context</span><h3>{parcel.zoning ?? "Zoning not established"}</h3><p className="footnote">Recorded classification. Planning limits and source evidence are held in the parcel record.</p></section>
      </aside>
    </article>)}
  </div>;
}
