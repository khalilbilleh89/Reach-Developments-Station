"use client";
import { useEffect, useState } from "react";
import { ApiError, inventory } from "@/lib/api";
import type { Unit, UnitRegister, UnitReleaseResult, UnitStatusEvent } from "@/lib/api";
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
  const [picked,setPicked] = useState<Set<string>>(new Set());
  const [outcome,setOutcome] = useState<UnitReleaseResult | null>(null);
  const key = JSON.stringify([projectId,search,status,offset,revision]);
  useEffect(() => {
    let active = true;
    const timer = setTimeout(() => {void inventory.units(projectId,{search,commercial_status:status,limit:"50",offset:String(offset)}).then(data => {if(active) setResult({key,data});}).catch(e => {if(active) setFailure({key,message:e instanceof ApiError ? e.message : "Could not load commercial stock."});});},150);
    return () => {active=false;clearTimeout(timer);};
  },[projectId,search,status,offset,revision,key]);
  const rows = result?.key === key ? result.data : null;
  /** The same roles that may move one unit by hand may release a set of them. */
  const canRelease = ["master_admin","system_admin","project_manager","sales_operations"].some(role => roles.has(role));
  /** A unit is pickable when its own gates already pass; the rest say why not. */
  const ready = (rows?.units ?? []).filter(unit => unit.release_eligible && ["unreleased","held"].includes(unit.commercial_status));
  const chosen = ready.filter(unit => picked.has(unit.id));
  const releaseChosen = async () => {
    setBusy(true);setError(null);
    try {
      const result = await inventory.releaseUnits(projectId,chosen.map(unit => unit.id));
      setOutcome(result);setPicked(new Set());setRevision(value=>value+1);
    }
    catch(e) {setError(e instanceof ApiError ? e.message : "Could not release the selected units.");}
    finally {setBusy(false);}
  };
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
      {outcome ? <Notice tone={outcome.skipped ? "warning" : "success"}>
        <strong>{outcome.released} {outcome.released===1 ? "unit is" : "units are"} now on sale.</strong>
        {outcome.skipped ? <ul className="unit-release-requirements">{outcome.outcomes.filter(row=>!row.released).map(row=><li key={row.unit_id}>{row.unit_reference}: {row.blockers.join("; ")}</li>)}</ul> : null}
      </Notice> : null}
      {failure?.key === key ? <Notice tone="error">{failure.message}<Button onClick={()=>setRevision(value=>value+1)}>Retry</Button></Notice> : !rows ? <Loading label="Loading commercial stock" /> : <>
        {canRelease ? <div className="row-actions">
          <Button variant="primary" disabled={busy || chosen.length===0} onClick={()=>void releaseChosen()}>Release {chosen.length} selected</Button>
          <span className="footnote">{ready.length===0 ? "No unit on this page is ready to go on sale." : `${ready.length} ready to release on this page.`}</span>
        </div> : null}
        <TableScroll label="Commercial stock"><thead><tr>{canRelease ? <th><label><input type="checkbox" aria-label="Select every unit ready to release"
          checked={ready.length>0 && chosen.length===ready.length} disabled={busy || ready.length===0}
          onChange={e=>setPicked(e.target.checked ? new Set(ready.map(unit=>unit.id)) : new Set())} /></label></th> : null}<th>Unit</th><th>Commercial</th><th>Legal</th><th>Collections</th><th>Delivery</th></tr></thead><tbody>{rows.units.map(unit=><tr key={unit.id}>{canRelease ? <td><label><input type="checkbox" aria-label={`Release ${unit.unit_reference}`}
          checked={picked.has(unit.id)} disabled={busy || !ready.some(row=>row.id===unit.id)}
          onChange={e=>setPicked(current=>{const next = new Set(current); if(e.target.checked) next.add(unit.id); else next.delete(unit.id); return next;})} /></label></td> : null}<th scope="row"><Button disabled={busy} onClick={()=>void loadUnit(unit.id)}>{unit.unit_reference}</Button></th><td>{statusLabel(unit.commercial_status)}{unit.release_blockers.length && ["unreleased","held"].includes(unit.commercial_status) ? <span className="footnote"> — {unit.release_blockers.join("; ")}</span> : null}</td><td>{statusLabel(unit.legal_status)}</td><td>{statusLabel(unit.collection_status)}</td><td>{statusLabel(unit.delivery_status)}</td></tr>)}</tbody></TableScroll>
        {rows.units.length===0 ? <p>No matching units.</p> : null}
        <RegisterPagination offset={offset} total={rows.total} pageSize={50} onChange={setOffset} />
      </>}
    </>}
  </Card>;
}
