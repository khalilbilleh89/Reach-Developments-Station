"use client";
import { useState } from "react";
import type { LaunchRegister, UnitRegister, UnitSummary } from "@/lib/api";
import { Badge, Button, EmptyState, Icon, RecordLink, TableScroll } from "@/components/ui";
import { useCurrencyCode } from "@/lib/currency";
import { money } from "@/lib/format";
import { statusLabel, statusTone } from "./statusLabels";

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
  const [layout, setLayout] = useState<"stack" | "browse" | "table">("stack");
  const [lens, setLens] = useState<"commercial_status" | "delivery_status">("commercial_status");
  const [chosenFloor, setChosenFloor] = useState<string | null>(null);
  const [chosenBuilding, setChosenBuilding] = useState<string | null>(null);
  const buildingKey = (unit: UnitSummary) => JSON.stringify([unit.phase_id, unit.building_id]);
  const buildings = new Map<string, { label: string; count: number }>();
  for (const unit of register.units) {
    const key = buildingKey(unit);
    const entry = buildings.get(key) ?? { label: [unit.phase_code ? `Phase ${unit.phase_code}` : "Phase not recorded", unit.building_code ? `Building ${unit.building_code}` : "Building not recorded"].join(" · "), count: 0 };
    entry.count += 1;
    buildings.set(key, entry);
  }
  const activeBuilding = chosenBuilding && buildings.has(chosenBuilding) ? chosenBuilding : null;
  const visibleUnits = activeBuilding ? register.units.filter(unit => buildingKey(unit) === activeBuilding) : register.units;
  const priceByUnit=new Map(prices?.rows.map(price=>[price.unit_id,price]) ?? []);
  const floors = new Map<string, { label: string; units: UnitSummary[] }>();
  for (const unit of visibleUnits) {
    const key = JSON.stringify([unit.phase_id, unit.building_id, unit.floor_id]);
    const group = floors.get(key) ?? { label: [unit.phase_code, unit.building_code, unit.floor_code].filter(Boolean).join(" / ") || "Location not recorded", units: [] };
    group.units.push(unit);
    floors.set(key, group);
  }
  const activeFloor = chosenFloor && floors.has(chosenFloor) ? chosenFloor : null;
  return <section className="stock-register" aria-label="Stock schedule">
    <div className="stock-register-heading"><div><h2>Explore properties</h2><p>Compare your units, their features and launch prices.</p></div><div className="stock-view-controls"><Button small onClick={() => setLayout("stack")} aria-pressed={layout === "stack"}>Building stack</Button><Button small onClick={() => setLayout("browse")} aria-pressed={layout === "browse"}>Property cards</Button><Button small onClick={() => setLayout("table")} aria-pressed={layout === "table"}>Schedule</Button>{layout === "table" ? <Button small onClick={onExpanded} aria-pressed={expanded}>{expanded ? "Compact areas" : "Show all areas"}</Button> : null}</div></div>
    {register.units.length < register.total ? <p className="stock-note">Showing {register.units.length} of {register.total} matching units on this page. Floor groups cover this page only.</p> : null}
    {layout !== "table" && buildings.size > 1 ? <nav className="property-building-nav" aria-label="Buildings on this inventory page"><div><Icon name="building" /><span>Buildings<span className="footnote">Current inventory page</span></span></div><div className="property-building-options"><button type="button" aria-pressed={!activeBuilding} onClick={() => { setChosenBuilding(null); setChosenFloor(null); }}>All buildings <span>{register.units.length}</span></button>{[...buildings].map(([key, building]) => <button type="button" key={key} aria-pressed={activeBuilding === key} onClick={() => { setChosenBuilding(key); setChosenFloor(null); }}>{building.label}<span>{building.count}</span></button>)}</div></nav> : null}
    {register.units.length===0 ? <EmptyState title="No stock matches these filters" hint="Clear or adjust your filters to see more units." /> : layout === "stack" ? <div className="building-atlas">
      <div className="atlas-toolbar"><div><span className="eyebrow">The development, unit by unit</span><p>Schematic · equal-size tiles, not a floor plan. Floors follow register order.</p></div><label className="atlas-lens">Colour by<select className="input" value={lens} onChange={event => setLens(event.target.value as typeof lens)}><option value="commercial_status">Commercial status</option><option value="delivery_status">Delivery status</option></select></label></div>
      <div className="atlas-legend" aria-label="Status legend">{[...new Set(visibleUnits.map(unit => unit.is_active ? unit[lens] || "Not recorded" : "Inactive"))].map(status => <span key={status} data-tone={statusTone(status)}><i aria-hidden="true" />{statusLabel(status)}</span>)}</div>
      <div className="atlas-buildings">{[...new Set(visibleUnits.map(buildingKey))].map(building => {
        const units = visibleUnits.filter(unit => buildingKey(unit) === building);
        const first = units[0];
        return <section className="atlas-building" key={building}><header><div><span className="eyebrow">{first.phase_code ? "Phase " + first.phase_code : "Phase not recorded"}</span><h3>{first.building_code ? "Building " + first.building_code : "Building not recorded"}</h3></div><span>{units.length} units on this page</span></header>
          <div className="atlas-floors">{[...floors].filter(([,group]) => group.units.some(unit => units.includes(unit))).map(([key,group]) => <div className="atlas-floor" key={key}><div className="atlas-floor-label"><span>Floor</span><strong>{group.units[0].floor_code ?? "—"}</strong><small>{group.units.length} units</small></div><div className="atlas-units">{group.units.map(unit => {
            const state = unit.is_active ? unit[lens] || "Not recorded" : "Inactive";
            const price = priceByUnit.get(unit.id);
            return <article className="atlas-unit" data-tone={statusTone(state)} key={unit.id}><div className="atlas-unit-top"><RecordLink projectId={projectId} kind="unit" id={unit.id} tab="detail">{unit.unit_reference}</RecordLink><span className="atlas-unit-dot" aria-hidden="true" /></div><span className="atlas-unit-state">{statusLabel(state)}</span><div className="atlas-unit-facts"><span>{unit.bedrooms == null ? "Beds —" : unit.bedrooms + " bed"}</span><span>{componentArea(unit,"internal")}</span></div>{seesPrice ? <strong className="atlas-unit-price">{priceError ? "Price unavailable" : price?.repricing_required ? "Price needs review" : price?.price ? money(price.price,codeOf(price.currency_id)) : "Not priced"}</strong> : null}</article>;
          })}</div></div>)}</div>
          <footer><span>Open any unit to inspect its full record</span><span>{seesPrice ? "Current launch prices · ex tax" : "Property and status information"}</span></footer>
        </section>;
      })}</div>
    </div> : layout === "browse" ? <div className="stock-browser">
      <nav className="stock-hierarchy" aria-label="Floors on this inventory page"><span className="eyebrow">Browse this page</span><button type="button" aria-pressed={activeFloor === null} onClick={() => setChosenFloor(null)}>All locations <span>{visibleUnits.length}</span></button>{[...floors].map(([key, group]) => <button key={key} type="button" aria-pressed={activeFloor === key} onClick={() => setChosenFloor(key)}>{group.label}<span>{group.units.length}</span></button>)}</nav>
      <div className="stock-floor-groups">{[...floors].filter(([key]) => activeFloor === null || key === activeFloor).map(([key, group]) => <section key={key} className="stock-floor-group">
        <h3>{group.label} <span>{group.units.length} on this page</span></h3>
        <div className="stock-property-grid">{group.units.map(unit => {
          const price = priceByUnit.get(unit.id);
          return <article key={unit.id} className="stock-property-card" data-status-tone={statusTone(unit.is_active ? unit.commercial_status || "Not recorded" : "Inactive")}>
            <div className="stock-property-emblem"><Icon name="inventory" /><span>{unit.asset_class.replaceAll("_", " ")}</span></div>
            <div className="stock-property-identity"><RecordLink projectId={projectId} kind="unit" id={unit.id} tab="detail">{unit.unit_reference}</RecordLink><Badge tone={unit.is_active ? statusTone(unit.commercial_status || "Not recorded") : "muted"}>{unit.is_active ? statusLabel(unit.commercial_status || "Not recorded") : "Inactive"}</Badge></div>
            <div className="property-feature-row"><span><Icon name="bed" />{unit.bedrooms ?? "—"} bed</span><span><Icon name="bath" />{unit.bathrooms ?? "—"} bath</span><span><Icon name="parking" />{unit.parking_count ?? "—"} parking</span></div>
            <p className="property-outlook"><Icon name="location" />{[unit.view_class_code, unit.orientation_code].filter(Boolean).join(" · ") || "View and orientation not recorded"}</p>
            <dl><div><dt>Internal</dt><dd>{componentArea(unit, "internal")}</dd></div><div><dt>Gross</dt><dd>{stockArea(unit.gross_area, unit.gross_area_unit)}</dd></div><div><dt>Balcony</dt><dd>{componentArea(unit,"balcony")}</dd></div></dl>
            <div className="property-delivery"><span>Delivery</span><Badge tone={statusTone(unit.delivery_status || "Not recorded")}>{statusLabel(unit.delivery_status || "Not recorded")}</Badge></div>
            {seesPrice ? <p className="stock-property-price">{priceError ? "Price unavailable" : price?.repricing_required ? "Price needs review" : price?.price ? money(price.price, codeOf(price.currency_id)) : "Not priced"}<small>Launch price · ex tax</small></p> : null}
          </article>;
        })}</div>
      </section>)}</div>
    </div> : <TableScroll label="Stock units" fixedFirst stickyHeader>
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
