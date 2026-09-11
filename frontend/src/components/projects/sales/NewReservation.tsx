"use client";

import { useEffect, useState } from "react";
import { ApiError, sales } from "@/lib/api";
import type { SalesUnitOption } from "@/lib/api";
import { Button, Card, Field, Loading, Notice, TableScroll } from "@/components/ui";
import { money } from "@/lib/format";
import { useCurrencyCode } from "@/lib/currency";
import { RegisterBuyerSaleForm } from "./RegisterBuyerSaleForm";
import { ReservationForm } from "./ReservationForm";

export function NewReservation({projectId, onCreated, onSaleCreated, allowOwner, onCancel}: {
  allowOwner: boolean; onSaleCreated: (id: string) => void;
  projectId: string; onCreated: (id: string) => void; onCancel: () => void;
}) {
  const [owner, setOwner] = useState(false);
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [retry, setRetry] = useState(0);
  const [result, setResult] = useState<{key: string; items: SalesUnitOption[]; next_offset: number | null} | null>(null);
  const [failure, setFailure] = useState<{key: string; message: string} | null>(null);
  const [selected, setSelected] = useState<SalesUnitOption | null>(null);
  const codeOf = useCurrencyCode();
  const key = JSON.stringify([projectId, search, offset, retry]);
  useEffect(() => {
    let active = true;
    const timer = setTimeout(() => { void sales.unitOptions(projectId, {search, offset: String(offset)}).then(rows => {
      if (active) {setResult({key, ...rows}); setFailure(null);}
    }).catch(error => {if (active) setFailure({key, message: error instanceof ApiError ? error.message : "Could not load available units."});}); }, 200);
    return () => {active = false; clearTimeout(timer);};
  }, [projectId, search, offset, retry, key]);
  const rows = result?.key === key ? result : null;
  const error = failure?.key === key ? failure.message : null;
  return <Card title="New Reservation" description="Choose an available unit, agree the price and prepare the buyer’s reservation.">
    {!selected ? <div className="stack">
      <Field label="Find available unit"><input className="input" type="search" value={search} placeholder="Unit reference, building or phase" onChange={e => {setSearch(e.target.value); setOffset(0);}} /></Field>
      {error ? <Notice tone="error">{error} <Button onClick={() => setRetry(retry + 1)}>Retry unit options</Button></Notice> : !rows ? <Loading label="Finding available units…" /> : <>
        {rows.items.length ? <TableScroll label="Available units"><thead><tr><th>Unit</th><th>Location</th><th>List price · ex tax</th><th>Select</th></tr></thead><tbody>{rows.items.map(unit => <tr key={unit.unit_id}>
          <th scope="row">{unit.unit_reference}<span className="cell-secondary">{unit.unit_type}</span></th><td>{unit.building_name} · {unit.floor_name}<span className="cell-secondary">{unit.phase_name}</span></td>
          <td>{money(unit.reference_price_ex_tax, codeOf(unit.currency_id))}</td><td><Button onClick={() => setSelected(unit)}>Select {unit.unit_reference}</Button></td>
        </tr>)}</tbody></TableScroll> : <Notice tone="info">No eligible units in this page. {rows.next_offset !== null ? "Continue to the next page or narrow your search." : "Try another reference. Units must be released and have a current approved price."}</Notice>}
        <div className="button-row"><Button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 30))}>Previous units</Button><Button disabled={rows.next_offset === null} onClick={() => setOffset(rows.next_offset!)}>Next units</Button></div>
      </>}
      <Button onClick={onCancel}>Cancel</Button>
    </div> : <>
      <p><strong>{selected.unit_reference}</strong> · {selected.building_name} · {selected.floor_name}</p>
      <p className="subtle">{selected.unit_type ?? "Unit type not recorded"} · {selected.gross_area === null ? "Gross area not confirmed" : `${selected.gross_area} ${selected.area_unit ?? ""}`}</p>
      <p className="subtle">Inventory list price: {money(selected.reference_price_ex_tax, codeOf(selected.currency_id))} excluding tax</p>
      {allowOwner ? <Button data-leaves-editor onClick={() => setOwner(!owner)}>{owner ? "Prepare standard reservation" : "Owner: register buyer & mark sold"}</Button> : null}
      {owner ? <RegisterBuyerSaleForm projectId={projectId} unitId={selected.unit_id} unitOption={selected} onSaved={onSaleCreated} onCancel={() => setOwner(false)} /> : <ReservationForm projectId={projectId} unitId={selected.unit_id} currencyId={selected.currency_id} unitOption={selected} onCreated={onCreated} onCancel={onCancel} onChangeUnit={() => {setSelected(null); setRetry(retry + 1);}} />}
    </>}
  </Card>;
}
