"use client";
import { useEffect, useState } from "react";
import { ApiError, inventory } from "@/lib/api";
import type { Unit, UnitRegister, UnitStatusEvent } from "@/lib/api";
import { Button, Card, Field, Loading, Notice, RegisterPagination, TableScroll } from "@/components/ui";
import { CommercialUnitControls } from "./CommercialUnitControls";
import { UnitStanding } from "../inventory/unit/UnitStanding";
import { UnitHistory } from "../inventory/unit/UnitHistory";
import { UnitStages } from "../construction/StageWorkspace";
import { statusLabel } from "../inventory/statusLabels";

/** Stock status controls live beside transactions, including units without a buyer yet. */
export function CommercialUnits({projectId,roles,onClose}: {projectId:string;roles:Set<string>;onClose:()=>void}) {
  const [search,setSearch] = useState("");
  const [status,setStatus] = useState("");
  const [offset,setOffset] = useState(0);
  const [revision,setRevision] = useState(0);
  const [result,setResult] = useState<{key:string;data:UnitRegister} | null>(null);
  const [failure,setFailure] = useState<{key:string;message:string} | null>(null);
  const [selected,setSelected] = useState<Unit | null>(null);
  const [history,setHistory] = useState<UnitStatusEvent[] | null>(null);
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState<string | null>(null);
  const key = JSON.stringify([projectId,search,status,offset,revision]);
  useEffect(() => {
    let active = true;
    const timer = setTimeout(() => {void inventory.units(projectId,{search,commercial_status:status,limit:"50",offset:String(offset)}).then(data => {if(active) setResult({key,data});}).catch(e => {if(active) setFailure({key,message:e instanceof ApiError ? e.message : "Could not load commercial stock."});});},150);
    return () => {active=false;clearTimeout(timer);};
  },[projectId,search,status,offset,revision,key]);
  const rows = result?.key === key ? result.data : null;
  const loadUnit = async (id:string) => {
    setBusy(true);setError(null);setHistory(null);
    try {setSelected(await inventory.unit(projectId,id));}
    catch(e) {setError(e instanceof ApiError ? e.message : "Could not read the unit.");}
    finally {setBusy(false);}
  };
  return <Card title="Commercial stock" description="Manage eligibility and commercial status before a buyer transaction, and inspect ongoing unit status." actions={<Button data-leaves-editor onClick={onClose}>Close</Button>}>
    {error ? <Notice tone="error">{error}</Notice> : null}
    {selected ? <div className="stack">
      <Button data-leaves-editor disabled={busy} onClick={() => {setSelected(null);setHistory(null);}}>Back to commercial stock</Button>
      <h2>{selected.unit_reference}</h2><UnitStanding unit={selected} />
      <CommercialUnitControls key={selected.id} unit={selected} roles={roles} busy={busy} onSaveControls={async changes => {await inventory.releaseControls(projectId,selected.id,changes);await loadUnit(selected.id);setRevision(value=>value+1);}}
        onTransition={async move => {setBusy(true);setError(null);try {await inventory.transitionUnit(projectId,selected.id,move);await loadUnit(selected.id);setRevision(value=>value+1);} catch(e) {setError(e instanceof ApiError ? e.message : "Could not change commercial status.");throw e;} finally {setBusy(false);}}} />
      <Button disabled={busy} onClick={async () => {try {setHistory(await inventory.unitHistory(projectId,selected.id));} catch(e) {setError(e instanceof ApiError ? e.message : "Could not load history.");}}}>Status history</Button>
      {history ? <UnitHistory history={history} /> : null}
      <UnitStages projectId={projectId} unitId={selected.id} roles={roles} />
    </div> : <>
      <Field label="Find unit"><input className="input" type="search" value={search} onChange={e=>{setSearch(e.target.value);setOffset(0);}} /></Field>
      <Field label="Commercial status"><select className="input" value={status} onChange={e=>{setStatus(e.target.value);setOffset(0);}}><option value="">All statuses</option>{["unreleased","held","available","reserved","sold"].map(value=><option key={value} value={value}>{statusLabel(value)}</option>)}</select></Field>
      {failure?.key === key ? <Notice tone="error">{failure.message}<Button onClick={()=>setRevision(value=>value+1)}>Retry</Button></Notice> : !rows ? <Loading label="Loading commercial stock" /> : <>
        <TableScroll label="Commercial stock"><thead><tr><th>Unit</th><th>Commercial</th><th>Legal</th><th>Collections</th><th>Delivery</th></tr></thead><tbody>{rows.units.map(unit=><tr key={unit.id}><th scope="row"><Button disabled={busy} onClick={()=>void loadUnit(unit.id)}>{unit.unit_reference}</Button></th><td>{statusLabel(unit.commercial_status)}</td><td>{statusLabel(unit.legal_status)}</td><td>{statusLabel(unit.collection_status)}</td><td>{statusLabel(unit.delivery_status)}</td></tr>)}</tbody></TableScroll>
        {rows.units.length===0 ? <p>No matching units.</p> : null}
        <RegisterPagination offset={offset} total={rows.total} pageSize={50} onChange={setOffset} />
      </>}
    </>}
  </Card>;
}
