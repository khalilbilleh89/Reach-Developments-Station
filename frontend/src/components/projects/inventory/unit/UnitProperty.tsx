"use client";
import { useEffect, useState } from "react";
import { inventory } from "@/lib/api";
import type { AreaSchedule, AreaType, InventoryOption, CustomValue, SubAsset, Unit } from "@/lib/api";
import { Button, Notice, KeyValue, KeyValueGrid, SectionHeader } from "@/components/ui";
import { EditForm, asValue } from "@/components/projects/EditForm";
import type { EditField } from "@/components/projects/EditForm";
import { PhysicalRecord } from "./PhysicalRecord";

export const UNIT_FIELDS: EditField[] = [
  { name: "asset_class", label: "Property class", kind: "select", options: ["apartment", "villa", "townhouse", "commercial", "other"].map(value => ({ value, label: value })), group: "Identity" },
  { name: "unit_type_code", label: "Unit type", group: "Identity" },
  { name: "sequence", label: "Display order", kind: "number", group: "Identity" },
  { name: "plot_coverage_fraction", label: "Plot coverage fraction", hint: "0 to 1; for example 0.40 means 40%", group: "Features" },
  { name: "unit_reference", label: "Unit reference", group: "Identity", width: "medium" },
  { name: "unit_number", label: "Unit number", group: "Identity", width: "short" },
  { name: "bedrooms", label: "Bedrooms", kind: "number", group: "Identity" },
  { name: "bathrooms", label: "Bathrooms", kind: "number", group: "Identity" },
  { name: "furnishing_specification_code", label: "Furnishing", group: "Features", width: "medium" },
  { name: "floor_band_code", label: "Floor band", group: "Features", width: "short" },
  { name: "orientation_code", label: "Orientation", group: "Features", width: "short" },
  { name: "view_class_code", label: "View", group: "Features", width: "short" },
  { name: "accessibility_code", label: "Accessibility", group: "Features", width: "short" },
  { name: "garden_class_code", label: "Garden", group: "Features", width: "short" },
  { name: "has_maid_room", label: "Maid room", kind: "checkbox", group: "Features" },
  { name: "is_duplex", label: "Duplex", kind: "checkbox", group: "Features" },
  { name: "is_penthouse", label: "Penthouse", kind: "checkbox", group: "Features" },
  { name: "is_corner", label: "Corner unit", kind: "checkbox", group: "Features" },
  { name: "pool_access", label: "Pool access", kind: "checkbox", group: "Features" },
];

export const CONFIGURED_FIELDS: Record<string,string> = {
  unit_type_code:"unit_type", view_class_code:"view_class", orientation_code:"orientation",
  floor_band_code:"floor_band", furnishing_specification_code:"furnishing_specification",
  accessibility_code:"accessibility", garden_class_code:"garden_class",
};

export function configuredField(field:EditField,options:InventoryOption[],current:string|null):EditField {
  const category=CONFIGURED_FIELDS[field.name];
  if(!category) return field;
  const candidates=options.filter(option=>option.category===category);
  const choices=candidates.filter(option=>option.is_active).map(option=>({value:option.code,label:option.label}));
  if(current && !choices.some(option=>option.value===current)) {
    const prior=candidates.find(option=>option.code===current);
    choices.push({value:current,label:`${prior?.label ?? current} (current, inactive)`});
  }
  return {...field,kind:"select",options:[{value:"",label:"Not assigned"},...choices],hint:choices.length ? undefined : "Add choices in Inventory Configuration."};
}

/** Each section edits exactly the fields displayed within that section. */
export function UnitProperty({projectId,unit,areaTypes,schedules,assets,values,canWrite,canApprove,canDelete=false,onChanged}: {
  projectId:string;unit:Unit;areaTypes:AreaType[];schedules:AreaSchedule[];assets:SubAsset[];
  values:CustomValue[];canDelete?:boolean; canWrite:boolean;canApprove:boolean;onChanged:()=>Promise<void>;
}) {
  const [editing,setEditing]=useState<string | null>(null);
  const [configuration,setConfiguration]=useState<{projectId:string;options:InventoryOption[]} | null>(null);
  const [configError,setConfigError]=useState(false);
  const [retry,setRetry]=useState(0);
  useEffect(()=>{let active=true;inventory.configuration(projectId).then(options=>{if(active){setConfiguration({projectId,options});setConfigError(false);}}).catch(()=>{if(active)setConfigError(true);});return()=>{active=false;};},[projectId,retry]);
  const options=configuration?.projectId===projectId ? configuration.options : null;
  const additional=values.filter(value=>value.is_editable);
  return <div className="stack">
    {configError ? <Notice tone="error">Project choices could not be loaded.<Button onClick={()=>setRetry(value=>value+1)}>Retry choices</Button></Notice> : null}
    {["Identity","Features"].map(group=>{
      const fields=UNIT_FIELDS.filter(field=>field.group===group).map(field=>({...configuredField(field,options ?? [],unit[field.name as keyof Unit] as string|null),group:undefined}));
      return <section key={group}>
        <SectionHeader level={2} title={group} actions={canWrite ? <Button small disabled={!options || configError} data-leaves-editor onClick={()=>setEditing(editing===group ? null : group)}>{editing===group ? "Close editor" : `Edit ${group.toLowerCase()}`}</Button> : undefined} />
        {editing===group ? <EditForm key={group} fields={fields} initial={Object.fromEntries(fields.map(field=>[field.name,asValue(unit[field.name as keyof Unit] as never)]))}
          submitLabel={`Save ${group.toLowerCase()}`} onSave={async changes=>{await inventory.updateUnit(projectId,unit.id,changes);setEditing(null);await onChanged();}} onCancel={()=>setEditing(null)} /> : <KeyValueGrid columns={3}>
          {fields.map(field=><KeyValue key={field.name} label={field.label} value={typeof unit[field.name as keyof Unit]==="boolean" ? unit[field.name as keyof Unit] ? "Yes" : "No" : String(options?.find(option=>option.category===CONFIGURED_FIELDS[field.name] && option.code===unit[field.name as keyof Unit])?.label ?? unit[field.name as keyof Unit] ?? "—")} />)}
        </KeyValueGrid>}
      </section>;
    })}
    <PhysicalRecord canDelete={canDelete} projectId={projectId} unit={unit} areaTypes={areaTypes} schedules={schedules} assets={assets} options={options ?? []} canWrite={canWrite} canApprove={canApprove} onChanged={onChanged} />
    {values.length ? <section>
      <SectionHeader level={2} title="Additional fields" actions={additional.length ? <Button small data-leaves-editor onClick={()=>setEditing(editing==="additional" ? null : "additional")}>{editing==="additional" ? "Close editor" : "Edit additional fields"}</Button> : undefined} />
      {editing==="additional" ? <EditForm fields={additional.map(value=>({name:value.field_key,label:value.display_label,hint:value.help_text ?? undefined,affix:value.unit_of_measure ?? undefined,
        kind:value.data_type==="boolean" ? "checkbox" : value.data_type==="date" ? "date" : value.data_type==="option" ? "select" : value.data_type==="text" ? "text" : "number",
        options:value.data_type==="option" ? value.options.map(option=>({value:option.code,label:option.label})) : undefined}))}
        initial={Object.fromEntries(additional.map(value=>[value.field_key,asValue(value.value)]))} submitLabel="Save additional fields"
        onSave={async changes=>{await inventory.writeUnitValues(projectId,unit.id,changes);setEditing(null);await onChanged();}} onCancel={()=>setEditing(null)} /> : <KeyValueGrid columns={3}>
        {values.map(value=><KeyValue key={value.definition_id} label={value.display_label} value={value.value==null ? null : `${String(value.value)}${value.unit_of_measure ? ` ${value.unit_of_measure}` : ""}`} />)}
      </KeyValueGrid>}
    </section> : null}
  </div>;
}
