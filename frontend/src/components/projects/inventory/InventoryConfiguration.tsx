"use client";

import { useEffect, useState } from "react";
import { ApiError, inventory } from "@/lib/api";
import type { InventoryOption } from "@/lib/api";
import { Badge, Button, Card, EmptyState, Field, Loading, Notice, TableScroll } from "@/components/ui";
import { EditForm } from "../EditForm";

export const INVENTORY_CATEGORIES = [
  ["unit_type", "Unit types"], ["view_class", "Views"], ["orientation", "Orientations"],
  ["floor_band", "Floor bands"], ["furnishing_specification", "Furnishing"],
  ["accessibility", "Accessibility"], ["garden_class", "Garden types"],
  ["sub_asset_subtype", "Parking / storage types"],
] as const;

export function InventoryConfiguration({projectId,canConfigure}: {projectId:string;canConfigure:boolean}) {
  const [category,setCategory]=useState<string>("view_class");
  const [result,setResult]=useState<{projectId:string;rows:InventoryOption[]} | null>(null);
  const [error,setError]=useState<string|null>(null);
  const [editing,setEditing]=useState<InventoryOption | "new" | null>(null);
  const [revision,setRevision]=useState(0);
  const load=()=>{setResult(null);setError(null);setRevision(value=>value+1);};
  useEffect(()=>{let active=true;
    inventory.configuration(projectId).then(rows=>{if(active){setResult({projectId,rows});setError(null);}})
      .catch(e=>{if(active)setError(e instanceof ApiError ? e.message : "Could not load inventory configuration.");});
    return()=>{active=false;};
  },[projectId,revision]);
  const rows=result?.projectId===projectId ? result.rows : null;
  return <Card title="Project choices" description="Set the choices available when editing units in this project. Other projects have their own lists.">
    <Field label="Configure"><select className="input" value={category} disabled={editing!==null} onChange={e=>{setCategory(e.target.value);setEditing(null);}}>{INVENTORY_CATEGORIES.map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></Field>
    {error ? <Notice tone="error">{error}<Button onClick={()=>void load()}>Retry</Button></Notice> : !rows ? <Loading label="Loading project choices" /> : <>
      {canConfigure && !editing ? <Button data-leaves-editor onClick={()=>setEditing("new")}>Add choice</Button> : null}
      {editing ? <EditForm key={editing==="new" ? `new-${category}` : editing.id}
        fields={editing==="new" ? [{name:"code",label:"Code",hint:"A stable identifier, such as SEA. It cannot be changed after saving."},{name:"label",label:"Name shown in the dropdown"},{name:"sort_order",label:"Display order",kind:"number"}] : [{name:"label",label:"Name shown in the dropdown"},{name:"sort_order",label:"Display order",kind:"number"},{name:"is_active",label:"Available for new selections",kind:"checkbox"}]}
        initial={editing==="new" ? {code:"",label:"",sort_order:"0"} : {label:editing.label,sort_order:String(editing.sort_order),is_active:editing.is_active}}
        submitLabel={editing==="new" ? "Add choice" : "Save choice"} onCancel={()=>setEditing(null)}
        onSave={async changes=>{if(editing==="new") await inventory.createOption(projectId,{category,...changes}); else await inventory.updateOption(projectId,editing.id,changes);setEditing(null);await load();}} /> : null}
      {rows.filter(row=>row.category===category).length ? <TableScroll label="Configured choices"><thead><tr><th>Name</th><th>Code</th><th>Display order</th><th>Status</th>{canConfigure ? <th>Edit</th> : null}</tr></thead><tbody>{rows.filter(row=>row.category===category).map(row=><tr key={row.id}><th scope="row">{row.label}</th><td>{row.code}</td><td>{row.sort_order}</td><td><Badge tone={row.is_active ? "success" : "muted"}>{row.is_active ? "Active" : "Inactive"}</Badge></td>{canConfigure ? <td><Button small data-leaves-editor onClick={()=>setEditing(row)}>Edit {row.label}</Button></td> : null}</tr>)}</tbody></TableScroll> : <EmptyState title="No choices configured" hint="Add the choices that apply to this project. Unit fields may also be left unassigned." />}
      <p className="footnote">Renaming updates the displayed name. Deactivating a choice preserves existing unit selections and removes it from new selections. Codes stay unchanged so pricing rules continue to match.</p>
    </>}
  </Card>;
}
