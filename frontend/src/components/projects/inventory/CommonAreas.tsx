"use client";

import { useCallback, useEffect, useState } from "react";
import { commonAreas } from "@/lib/api/commonAreas";
import type { CommonArea } from "@/lib/api/commonAreas";
import { inventory } from "@/lib/api";
import { Button, Loading, Notice, RecordPage, SectionHeader, TableScroll } from "@/components/ui";
import { EditForm } from "../EditForm";
import type { EditField } from "../EditForm";
import { DeleteRecordButton } from "../DeleteRecordButton";

const categories = [{value:"common",label:"Common area"},{value:"garage",label:"Garage"},
  {value:"community",label:"Community"},{value:"roads_pavements",label:"Roads & pavements"}];

export function CommonAreas({ projectId, canWrite }: { projectId: string; canWrite: boolean }) {
  const [rows, setRows] = useState<CommonArea[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<CommonArea | "new" | null>(null);
  const [apartments, setApartments] = useState<{value:string;label:string}[]>([]);
  const fetchSources = useCallback(async () => {
        const records=await commonAreas.list(projectId);
        const options:{value:string;label:string}[]=[];
        let offset=0, total=1;
        while(offset<total) {
          const page=await inventory.units(projectId,{asset_class:"apartment",is_active:"true",limit:"200",offset:String(offset)});
          options.push(...page.units.map(unit=>({value:unit.id,label:unit.unit_reference})));
          total=page.total;offset+=200;
        }
        return {records,options};
  }, [projectId]);
  const load = useCallback(async () => {
    try { const result=await fetchSources();setApartments(result.options);setRows(result.records);setError(null); }
    catch(caught) {setRows(null);setError(caught instanceof Error ? caught.message : "Could not load common areas or apartment choices.");}
  },[fetchSources]);
  useEffect(() => {
    let current=true;
    fetchSources().then(result=>{if(current){setApartments(result.options);setRows(result.records);setError(null);}})
      .catch(caught=>{if(current){setRows(null);setError(caught instanceof Error ? caught.message : "Could not load common areas or apartment choices.");}});
    return()=>{current=false;};
  },[fetchSources]);
  const row=editing && editing!=="new" ? editing : null;
  const initial={label:row?.label ?? "",category:row?.category ?? "common",area_sqm:row?.area_sqm ?? "",
    apartment_id:row?.apartment_id ?? "",source_reference:row?.source_reference ?? ""};
  const options=[{value:"",label:"Project area — not allocated"},...apartments];
  if(row?.apartment_id && !options.some(option=>option.value===row.apartment_id)) options.push({value:row.apartment_id,label:"Previously allocated apartment (review allocation)"});
  const fields:EditField[]=[{name:"label",label:"Area name"},{name:"category",label:"Category",kind:"select",options:categories},
    {name:"area_sqm",label:"Measured area",affix:"m²",hint:"Enter 0 when this area does not apply."},
    {name:"apartment_id",label:"Apartment allocation",kind:"select",options,hint:"Common area only. Record each allocation once; do not also add the unallocated total."},
    {name:"source_reference",label:"Source reference",hint:"Drawing, schedule or measurement reference",width:"full"}];
  return <section className="stack">
    <SectionHeader title="Shared area register" description="Measured shared and site areas feeding Overview → Feasibility." actions={canWrite ? <Button disabled={!!error || rows===null} onClick={()=>setEditing("new")}>Add area</Button> : undefined} />
    <Notice tone="info">Record each physical area once. Garage includes the full measured garage area, not another sum of parking attachments. Community areas exclude common building areas and roads/pavements. Enter separate apartment allocation rows instead of repeating a project common-area total.</Notice>
    {error ? <Notice tone="error">{error}<Button onClick={()=>void load()}>Retry</Button></Notice> : rows===null ? <Loading label="Loading common areas" /> : rows.length ?
      <TableScroll label="Common Areas register"><thead><tr><th scope="col">Area</th><th scope="col">Category</th><th scope="col" className="num">Area m²</th><th scope="col">Allocation</th><th scope="col">Source</th><th scope="col">Actions</th></tr></thead><tbody>{rows.map(area=><tr key={area.id}>
        <th scope="row">{area.label}</th><td>{categories.find(item=>item.value===area.category)?.label}</td><td className="num">{area.area_sqm}</td><td>{area.apartment_id ? apartments.find(item=>item.value===area.apartment_id)?.label ?? "Apartment allocation" : "Project"}</td><td>{area.source_reference}</td><td>{canWrite ? <><Button onClick={()=>setEditing(area)}>Edit</Button><DeleteRecordButton label={area.label} description="Removes this measurement from current Feasibility totals. Its source values and deletion reason remain in the audit trail." onDelete={reason=>commonAreas.remove(projectId,area.id,reason)} onDeleted={load} /></> : "Read only"}</td>
      </tr>)}</tbody></TableScroll> : <Notice tone="info">No common areas recorded. Feasibility will show missing inputs until measurements are added.</Notice>}
    {editing ? <RecordPage title={row ? `Edit ${row.label}` : "Add common area"} onClose={()=>setEditing(null)}><EditForm fields={fields} initial={initial} submitLabel="Save area" onCancel={()=>setEditing(null)} onSave={async changes=>{
      const values:Record<string,unknown>={...initial,...changes};values.apartment_id=values.apartment_id || null;
      if(row) await commonAreas.update(projectId,row.id,values);else await commonAreas.create(projectId,values);
      setEditing(null);await load();
    }} /></RecordPage> : null}
  </section>;
}
