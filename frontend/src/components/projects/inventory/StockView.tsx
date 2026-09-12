"use client";
import type { LaunchRegister, UnitRegister, UnitSummary } from "@/lib/api";
import { Badge, Button, EmptyState, RecordLink, TableScroll } from "@/components/ui";
import { useCurrencyCode } from "@/lib/currency";
import { money } from "@/lib/format";

/** Display exact decimal strings without insignificant trailing zeroes. */
export function stockArea(value:string|null|undefined,unit:string|null|undefined):string {
  if(value==null) return "—";
  const clean=value.includes(".") ? value.replace(/0+$/,"").replace(/\.$/,"") : value;
  return `${clean}${unit ? ` ${unit}` : ""}`;
}

export function StockSummary({register,prices}: {register:UnitRegister;prices:LaunchRegister|null}) {
  const codeOf=useCurrencyCode();
  return <section className="stock-summary" aria-label="Stock overview">
    <div className="stock-summary-lead"><span className="stock-eyebrow">Inventory at a glance</span><strong>{register.total}</strong><span>units in this selection</span></div>
    <div><span className="stock-eyebrow">Launch pricing</span><strong>{prices ? prices.priced_count : "—"}</strong><span>units with a current list price</span></div>
    <div><span className="stock-eyebrow">To prepare</span><strong>{prices ? prices.unpriced_count : "—"}</strong><span>unpriced{prices?.repricing_count ? ` · ${prices.repricing_count} need repricing` : ""}</span></div>
    <div className="stock-summary-value"><span className="stock-eyebrow">Potential list value · ex tax</span>{prices?.totals.length ? prices.totals.map(total=><strong key={total.currency_id}>{money(total.amount,codeOf(total.currency_id))}</strong>) : <strong>—</strong>}<span>current launch prices only</span></div>
  </section>;
}

function componentArea(unit:UnitSummary,component:string):string {
  const measured=unit.physical_components?.[component];
  return stockArea(measured?.area,measured?.unit);
}

export function StockTable({projectId,register,prices,seesPrice,priceError,expanded,onExpanded}: {
  projectId:string;register:UnitRegister;prices:LaunchRegister|null;seesPrice:boolean;priceError:string|null;
  expanded:boolean;onExpanded:()=>void;
}) {
  const codeOf=useCurrencyCode();
  const priceByUnit=new Map(prices?.rows.map(price=>[price.unit_id,price]) ?? []);
  return <section className="stock-register" aria-label="Stock schedule">
    <div className="stock-register-heading"><div><h2>Unit schedule</h2><p>Compare your units, their features and launch prices.</p></div><Button small onClick={onExpanded} aria-pressed={expanded}>{expanded ? "Compact areas" : "Show all areas"}</Button></div>
    {register.units.length===0 ? <EmptyState title="No stock matches these filters" hint="Clear or adjust your filters to see more units." /> : <TableScroll label="Stock units" fixedFirst stickyHeader>
      <thead><tr><th scope="col">Unit / location</th><th scope="col">Features</th><th scope="col">Internal</th><th scope="col">Balcony</th><th scope="col">Net</th><th scope="col">Gross</th>{expanded ? <><th scope="col">Roof garden</th><th scope="col">Terrace</th><th scope="col">Front garden</th><th scope="col">Porches</th></> : null}{seesPrice ? <th scope="col">Launch price · ex tax</th> : null}</tr></thead>
      <tbody>{register.units.map(unit=>{
        const price=priceByUnit.get(unit.id);
        return <tr key={unit.id}>
          <th scope="row"><RecordLink projectId={projectId} kind="unit" id={unit.id} tab="detail">{unit.unit_reference}</RecordLink><span className="stock-location">{[unit.phase_code,unit.building_code,unit.floor_code].filter(Boolean).join(" / ")}</span>{!unit.is_active ? <Badge tone="muted">Inactive</Badge> : null}</th>
          <td><span className="stock-unit-mix">{unit.bedrooms ?? "—"} bed <span>·</span> {unit.bathrooms ?? "—"} bath</span><span className="cell-secondary">{[unit.view_class_code,unit.orientation_code].filter(Boolean).join(" · ") || unit.asset_class}</span>{unit.parking_count || unit.storage_count ? <span className="cell-secondary">{unit.parking_count} parking · {unit.storage_count} storage</span> : null}</td>
          <td className="num">{componentArea(unit,"internal")}</td><td className="num">{componentArea(unit,"balcony")}</td><td className="num">{stockArea(unit.net_area,unit.net_area_unit)}</td><td className="num stock-gross">{stockArea(unit.gross_area,unit.gross_area_unit)}</td>
          {expanded ? ["roof_garden","terrace","front_garden","porches"].map(component=><td className="num" key={component}>{componentArea(unit,component)}</td>) : null}
          {seesPrice ? <td className="num stock-price">{priceError ? <span className="subtle">Unavailable</span> : price?.repricing_required ? <Badge tone="warning">Review price</Badge> : price?.price ? money(price.price,codeOf(price.currency_id)) : <Badge tone="neutral">Not priced</Badge>}</td> : null}
        </tr>;
      })}</tbody>
    </TableScroll>}
    <p className="stock-note">Net = internal + balcony. Gross also includes roof garden, terrace, front garden and porches. Parking and storage are separate. “—” means the measurement is unknown.</p>
    <p className="stock-note">List values include all matching inventory, including previously released units. Missing prices and prices needing review are excluded. Taxes depend on the applicable transaction and are shown in Sales.</p>
  </section>;
}
