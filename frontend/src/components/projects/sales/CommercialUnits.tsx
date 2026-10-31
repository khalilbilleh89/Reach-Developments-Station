"use client";
import { useEffect, useState } from "react";
import { ApiError, inventory, sales } from "@/lib/api";
import type { Unit, UnitRegister, UnitReleaseResult, UnitStatusEvent } from "@/lib/api";
import { Banner, BulkBar, Button, Card, DataToolbar, DensitySwitch, FilterChips, Loading, Notice, PromptDialog, RegisterPagination, SelectAllCell, SelectCell, StatusDot, TableScroll, ToolbarFilter } from "@/components/ui";
import { CommercialUnitControls } from "./CommercialUnitControls";
import { UnitStanding } from "../inventory/unit/UnitStanding";
import { UnitHistory } from "../inventory/unit/UnitHistory";
import { UnitStages } from "../construction/StageWorkspace";
import { statusLabel, statusTone } from "../inventory/statusLabels";

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
  const [returnPrompt,setReturnPrompt] = useState(false);
  const key = JSON.stringify([projectId,search,status,offset,revision]);
  useEffect(() => {
    let active = true;
    const timer = setTimeout(() => {void inventory.units(projectId,{search,commercial_status:status,limit:"50",offset:String(offset)}).then(data => {if(active) setResult({key,data});}).catch(e => {if(active) setFailure({key,message:e instanceof ApiError ? e.message : "Could not load commercial stock."});});},150);
    return () => {active=false;clearTimeout(timer);};
  },[projectId,search,status,offset,revision,key]);
  const rows = result?.key === key ? result.data : null;
  /** The same roles that may move one unit by hand may release a set of them. */
  const canRelease = ["master_admin","system_admin","project_manager","sales_operations"].some(role => roles.has(role));
  const canReturn = roles.has("sales_operations");
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
  const returnToMarket = async (reason:string) => {
    if (!selected) return;
    setBusy(true);setError(null);
    try {
      await sales.returnUnitToMarket(projectId,selected.id,reason);
      setReturnPrompt(false);setSelected(await inventory.unit(projectId,selected.id));
      setRevision(value=>value+1);
    } catch(e) {setError(e instanceof ApiError ? e.message : "Could not return this unit to market.");}
    finally {setBusy(false);}
  };
  return <Card title="Commercial stock" description="Manage eligibility and commercial status before a buyer transaction, and inspect ongoing unit status." actions={<Button data-leaves-editor onClick={onClose}>Close</Button>}>
    {error ? <Notice tone="error">{error}</Notice> : null}
    {selected ? <div className="stack">
      <Button data-leaves-editor disabled={busy} onClick={() => {setSelected(null);setHistory(null);}}>Back to commercial stock</Button>
      <h2>{selected.unit_reference}</h2><UnitStanding unit={selected} />
      {selected.commercial_status === "returned" ? <section className="stack">
        <p>The cancelled Sale remains in history. Activate a fresh price in Pricing, resolve the release blockers, then explicitly return this Unit to market. A new buyer will start a new Reservation.</p>
        {selected.release_blockers.length ? <Banner tone="info">Not ready: {selected.release_blockers.join("; ")}.</Banner> : null}
        <div><Button disabled={busy} onClick={()=>void loadUnit(selected.id)}>Refresh eligibility</Button>{canReturn ? <Button variant="primary" disabled={busy || selected.release_blockers.length>0} onClick={()=>{setError(null);setReturnPrompt(true);}}>Return to market</Button> : null}</div>
      </section> : null}
      <CommercialUnitControls key={selected.id} unit={selected} roles={roles} busy={busy} onSaveControls={async changes => {await inventory.releaseControls(projectId,selected.id,changes);await loadUnit(selected.id);setRevision(value=>value+1);}}
        onTransition={async move => {setBusy(true);setError(null);try {await inventory.transitionUnit(projectId,selected.id,move);await loadUnit(selected.id);setRevision(value=>value+1);} catch(e) {setError(e instanceof ApiError ? e.message : "Could not change commercial status.");throw e;} finally {setBusy(false);}}} />
      <Button disabled={busy} onClick={async () => {try {setHistory(await inventory.unitHistory(projectId,selected.id));} catch(e) {setError(e instanceof ApiError ? e.message : "Could not load history.");}}}>Status history</Button>
      {history ? <UnitHistory history={history} /> : null}
      <UnitStages projectId={projectId} unitId={selected.id} roles={roles} />
    </div> : <>
      <DataToolbar framed search={{value:search,onChange:value=>{setSearch(value);setOffset(0);},label:"Find unit",placeholder:"Unit reference"}}
        count={rows ? {shown:rows.units.length,total:rows.total,noun:"unit"} : undefined}
        onReset={search || status ? ()=>{setSearch("");setStatus("");setOffset(0);} : undefined}
        actions={<DensitySwitch />}>
        <ToolbarFilter label="Commercial status" active={status!==""}><select className="input" value={status} onChange={e=>{setStatus(e.target.value);setOffset(0);}}><option value="">All statuses</option>{["unreleased","held","available","reserved","sold","returned"].map(value=><option key={value} value={value}>{statusLabel(value)}</option>)}</select></ToolbarFilter>
      </DataToolbar>
      <FilterChips chips={[
        status ? {key:"status",label:`Commercial: ${statusLabel(status)}`,onRemove:()=>{setStatus("");setOffset(0);}} : null,
        search ? {key:"search",label:`“${search}”`,onRemove:()=>{setSearch("");setOffset(0);}} : null,
      ].filter((chip): chip is NonNullable<typeof chip> => chip !== null)} onClearAll={()=>{setSearch("");setStatus("");setOffset(0);}} />
      {outcome ? <Notice tone={outcome.skipped ? "warning" : "success"}>
        <strong>{outcome.released} {outcome.released===1 ? "unit is" : "units are"} now on sale.</strong>
        {outcome.skipped ? <ul className="unit-release-requirements">{outcome.outcomes.filter(row=>!row.released).map(row=><li key={row.unit_id}>{row.unit_reference}: {row.blockers.join("; ")}</li>)}</ul> : null}
      </Notice> : null}
      {failure?.key === key ? <Notice tone="error">{failure.message}<Button onClick={()=>setRevision(value=>value+1)}>Retry</Button></Notice> : !rows ? <Loading label="Loading commercial stock" /> : <>
        {canRelease ? <p className="footnote">{ready.length===0 ? "No unit on this page is ready to go on sale." : `${ready.length} ready to release on this page.`}</p> : null}
        <TableScroll label="Commercial stock"><thead><tr>{canRelease ? <SelectAllCell label="Select every unit ready to release"
          // Ticked only when every ready row on the page is picked; a dash while some are. Decided from
          // what is picked, never from the box's own state, so the selection always has a way back off.
          checked={chosen.length>0 && chosen.length===ready.length} indeterminate={chosen.length>0 && chosen.length<ready.length}
          onChange={()=>setPicked(chosen.length>0 ? new Set() : new Set(ready.map(unit=>unit.id)))} /> : null}<th>Unit</th><th>Commercial</th><th>Legal</th><th>Collections</th><th>Delivery</th></tr></thead><tbody>{rows.units.map(unit=><tr key={unit.id}>{canRelease ? <SelectCell label={`Select ${unit.unit_reference}`} checked={picked.has(unit.id)} disabled={busy || !ready.some(row=>row.id===unit.id)} onChange={()=>{ setPicked(current=>{const next = new Set(current); if(next.has(unit.id)) next.delete(unit.id); else next.add(unit.id); return next;}); }} /> : null}<th scope="row"><Button disabled={busy} onClick={()=>void loadUnit(unit.id)}>{unit.unit_reference}</Button></th><td><StatusDot tone={statusTone(unit.commercial_status)}>{statusLabel(unit.commercial_status)}</StatusDot>{unit.release_blockers.length && ["unreleased","held"].includes(unit.commercial_status) ? <span className="footnote"> — {unit.release_blockers.join("; ")}</span> : null}</td><td><StatusDot tone={statusTone(unit.legal_status)}>{statusLabel(unit.legal_status)}</StatusDot></td><td><StatusDot tone={statusTone(unit.collection_status)}>{statusLabel(unit.collection_status)}</StatusDot></td><td><StatusDot tone={statusTone(unit.delivery_status)}>{statusLabel(unit.delivery_status)}</StatusDot></td></tr>)}</tbody></TableScroll>
        {rows.units.length===0 ? <p>No matching units.</p> : null}
        {canRelease ? <BulkBar count={chosen.length} noun="unit" onClear={()=>setPicked(new Set())}>
          <Button small variant="primary" disabled={busy} onClick={()=>void releaseChosen()}>Release selected</Button>
        </BulkBar> : null}
        <RegisterPagination offset={offset} total={rows.total} pageSize={50} onChange={setOffset} />
      </>}
    </>}
    {returnPrompt && selected ? <PromptDialog title={`Return ${selected.unit_reference} to market`} description="The former Sale and Reservation remain cancelled. This publishes the Unit for a new buyer at its current approved price." label="Reason" confirmLabel="Return to market" busy={busy} error={error} onCancel={()=>{if(!busy){setReturnPrompt(false);setError(null);}}} onSubmit={reason=>void returnToMarket(reason)} /> : null}
  </Card>;
}
