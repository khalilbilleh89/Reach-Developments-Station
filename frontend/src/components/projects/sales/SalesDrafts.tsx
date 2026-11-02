"use client";

import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { useRef, useState } from "react";

import { ApiError } from "@/lib/api";

import { useAnswer } from "@/lib/answer";

import { salesDrafts } from "@/lib/api/salesDrafts";

import type { DraftPayload, SalesDraft } from "@/lib/api/salesDrafts";

import { Button, Card, DraftBoundary, EmptyState, Field, FormActions, Loading, Notice, PromptDialog, RecordLink, RecordPage, TableScroll } from "@/components/ui";

import { SalesImport } from "./SalesImport";

const fieldLabel = (value: string) => value.replaceAll("_", " ");

const display = (value: unknown) => value == null ? "" : typeof value === "object" ? JSON.stringify(value) : String(value);



export function SalesDrafts({projectId, allowed, onClose}: {projectId:string;allowed:boolean;onClose:()=>void}) {

  const params=useSearchParams();
  const [offset,setOffset]=useState(0),[selected,setSelected]=useState<string|null>(params.get("import_draft")),[importing,setImporting]=useState(false);

  const answer=useAnswer(allowed,()=>salesDrafts.list(projectId,offset),[projectId,offset]);

  if(!allowed)return <Notice tone="info">Sales import is available to Boss.</Notice>;

  if(importing)return <SalesImport projectId={projectId} kind="sales-drafts" onClose={()=>setImporting(false)} onImported={answer.retry}/>;

  if(selected)return <DraftRecord key={selected} projectId={projectId} id={selected} onClose={()=>{setSelected(null);answer.retry();}}/>;

  return <RecordPage title="Imported Sales drafts" onClose={onClose}>

    <p>Review the supplied details before adding a transaction to Sales. These drafts do not reserve units or record cash.</p>

    <Button variant="primary" onClick={()=>setImporting(true)}>Import Sales from Excel</Button>

    {answer.status==="loading"?<Loading label="Loading Sales drafts…"/>:answer.status==="denied"?<Notice tone="info">Drafts are not available to your role.</Notice>:answer.status==="failed"?<Notice tone="error">{answer.message}<Button onClick={answer.retry}>Retry</Button></Notice>:answer.status==="ready"?<>

      {!answer.data.length?<EmptyState title="No imported drafts" hint="Download the template and import your Sales data to begin review."/>:<TableScroll label="Imported Sales drafts"><thead><tr><th>Draft</th><th>Unit</th><th>Buyer</th><th>Review</th></tr></thead><tbody>{answer.data.map(row=><tr key={row.id}><th scope="row"><Button onClick={()=>setSelected(row.id)}>{row.source_key}</Button></th><td>{display(row.payload.Sales?.[0]?.unit_reference)}</td><td>{display(row.payload.Buyer?.[0]?.display_name)||"Existing buyer"}</td><td>{row.status==="added"?"Added to Sales · source retained":"Awaiting review"}</td></tr>)}</tbody></TableScroll>}

      <FormActions><Button disabled={!offset} onClick={()=>setOffset(Math.max(0,offset-50))}>Previous drafts</Button><Button disabled={answer.data.length<50} onClick={()=>setOffset(offset+50)}>Next drafts</Button></FormActions>

    </>:null}

  </RecordPage>;

}



function DraftRecord({projectId,id,onClose}:{projectId:string;id:string;onClose:()=>void}) {

  const answer=useAnswer(true,async()=>({row:await salesDrafts.read(projectId,id),fields:await salesDrafts.fields(projectId)}),[projectId,id]);

  return <RecordPage title="Review imported Sales draft" onClose={onClose}>{answer.status==="ready"?<DraftEditor key={`${answer.data.row.id}:${answer.data.row.version}`} projectId={projectId} row={answer.data.row} fields={answer.data.fields} refresh={answer.retry} onDeleted={onClose}/>:answer.status==="failed"?<Notice tone="error">{answer.message}<Button onClick={answer.retry}>Retry</Button></Notice>:answer.status==="denied"?<Notice tone="info">Draft not available to your role.</Notice>:<Loading label="Loading draft details…"/>}</RecordPage>;

}



export function DraftEditor({projectId,row,fields,refresh,onDeleted}:{projectId:string;row:SalesDraft;fields:Record<string,string[]>;refresh:()=>void;onDeleted:()=>void}) {

  const [payload,setPayload]=useState<DraftPayload>(row.payload),[busy,setBusy]=useState(false),[error,setError]=useState<string|null>(null),[action,setAction]=useState<"save"|"add"|"delete"|null>(null);

  const saving=useRef(false);

  const dirty=JSON.stringify(payload)!==JSON.stringify(row.payload);

  async function submit(reason:string) {

    if(saving.current||!action)return;saving.current=true;setBusy(true);setError(null);

    try {

      if(action==="delete")await salesDrafts.delete(projectId,row,reason);

      else if(action==="save")await salesDrafts.save(projectId,row,payload,reason);

      else await salesDrafts.add(projectId,row,reason);

      const deleted=action==="delete";setAction(null);if(deleted)onDeleted();else refresh();

    }catch(caught){setError(caught instanceof ApiError?caught.message:"Could not complete the request. Refresh the draft before retrying if the connection was interrupted.");}

    finally{saving.current=false;setBusy(false);}

  }

  return <DraftBoundary dirty={dirty} busy={busy}><div className="stack">

    <Card title={row.source_key} description={row.status==="added"?"Added to Sales. Imported source details are retained here.":"Unposted draft · review every supplied section"}>

      <Notice tone="info">Adding creates a preparing Sales transaction using Buyer, Agent, Parties, Reservation and Adjustments. SPA, EOI, legal, schedule, receipts and handover details remain attached as unposted source information. Complete their normal workflows explicitly; this action does not confirm payments or legal events.</Notice>

      {row.reservation_id?<RecordLink projectId={projectId} kind="reservation" id={row.reservation_id}>Open Sales transaction</RecordLink>:null}

      <FormActions><Button disabled={busy} onClick={async()=>{setError(null);try{await salesDrafts.export(projectId,row.id);}catch(caught){setError(caught instanceof ApiError?caught.message:"Could not download draft.");}}}>Download draft workbook</Button>

      {row.status==="draft"?<><Button disabled={busy||!dirty} onClick={()=>setAction("save")}>Save corrections</Button><Button variant="primary" disabled={busy||dirty} onClick={()=>setAction("add")}>Add reviewed draft to Sales</Button><Button variant="danger" disabled={busy||dirty} onClick={()=>setAction("delete")}>Delete draft</Button></>:null}</FormActions>

      {dirty?<p>Save corrections before adding or deleting this draft.</p>:null}

    </Card>

    {error&&!action?<Notice tone="error">{error}</Notice>:null}

    {Object.entries(fields).map(([section,columns])=><details key={section} open={section==="Sales"||undefined}><summary>{section} · {payload[section]?.length??0} rows</summary><div className="stack">

      {(payload[section]??[]).map((values,index)=><fieldset key={index} disabled={busy||row.status==="added"}><legend>{section} row {index+1}</legend><div className="form-grid">{columns.map(column=><Field key={column} label={fieldLabel(column)}><input className="input" aria-label={`${section} ${index+1} ${fieldLabel(column)}`} value={display(values[column])} onChange={event=>{const value=event.target.value;setPayload(current=>({...current,[section]:current[section].map((entry,i)=>{if(i!==index)return entry;const next={...entry};if(value)next[column]=value;else delete next[column];return next;})}));}}/></Field>)}</div>{row.status==="draft"?<Button disabled={busy} onClick={()=>setPayload(current=>({...current,[section]:current[section].filter((_,i)=>i!==index)}))}>Remove {section} row {index+1}</Button>:null}</fieldset>)}

      {row.status==="draft"?<Button disabled={busy} onClick={()=>setPayload(current=>({...current,[section]:[...(current[section]??[]),{}]}))}>Add {section} row</Button>:null}

    </div></details>)}

    {action?<PromptDialog title={`${action==="add"?"Add reviewed draft":action==="save"?"Save corrections":"Delete draft"} ${row.source_key}?`} label="Reason" confirmLabel={action==="add"?"Add to Sales":action==="save"?"Save":"Delete draft"} destructive={action==="delete"} description={action==="delete"?"Removes this unposted draft. An audit record of the deletion is retained.":action==="add"?"Creates a preparing transaction. All imported source details remain accessible here. No cash, signature or completed handover is posted.":"Validates all changed fields and saves a new review version."} busy={busy} error={error} onRefresh={refresh} onCancel={()=>{setAction(null);setError(null);}} onSubmit={reason=>void submit(reason)}/>:null}

  </div></DraftBoundary>;

}



export function ImportedSalesDetails({projectId,reservationId,allowed}:{projectId:string;reservationId:string;allowed:boolean}) {
  const answer=useAnswer(allowed,()=>salesDrafts.forReservation(projectId,reservationId),[projectId,reservationId]);
  if(answer.status==="off"||answer.status==="denied")return null;
  if(answer.status==="loading")return <Loading label="Checking imported source details…"/>;
  if(answer.status==="failed")return <Notice tone="error">{answer.message}<Button onClick={answer.retry}>Retry imported details</Button></Notice>;
  if(!answer.data)return null;
  return <Card title="Imported Sales details" description="EOI, SPA, legal, payment and handover source information remains unposted until processed through its normal workflow."><Link className="button" href={`/projects/?${new URLSearchParams({project:projectId,section:"sales",sales_view:"import-drafts",import_draft:answer.data.id})}`}>Review all imported sections</Link></Card>;
}
