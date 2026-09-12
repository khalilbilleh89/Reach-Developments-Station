"use client";

import { useEffect, useState, useRef } from "react";
import type { ComponentProps } from "react";
import { UnsavedChangesGuard } from "@/components/ui/UnsavedChangesGuard";
import { ApiError, inventory } from "@/lib/api";
import type { AreaSchedule, AreaType, InventoryOption, SubAsset, Unit, UnitDocument, UnitFeature } from "@/lib/api";
import { Button, Field, FieldRow, FormActions, FormSection, KeyValue, KeyValueGrid, Notice, SectionHeader } from "@/components/ui";

export const PHYSICAL_COMPONENTS = [
  ["internal", "Internal area"], ["balcony", "Balcony"], ["roof_garden", "Roof garden"],
  ["front_garden", "Front garden"], ["terrace", "Terrace"], ["porches", "Porches"],
] as const;

/** One unit's physical file. Amounts and completeness are always server answers. */
export function PhysicalRecord({ projectId, unit, areaTypes, schedules, assets, options = [], canWrite, canApprove, onChanged }: {
  projectId: string; unit: Unit; areaTypes: AreaType[]; schedules: AreaSchedule[];
  assets: SubAsset[]; options?: InventoryOption[]; canWrite: boolean; canApprove: boolean; onChanged: () => Promise<void>;
}) {
  const [features, setFeatures] = useState<UnitFeature[]>([]);
  const [documents, setDocuments] = useState<UnitDocument[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [label, setLabel] = useState("");
  const [doc, setDoc] = useState({ title: "", url: "", revision: "" });
  const [measuring, setMeasuring] = useState(false);
  const [featureEditing,setFeatureEditing] = useState(false);
  const [docEditing,setDocEditing] = useState(false);
  const [measurementBaseline,setMeasurementBaseline] = useState("");
  const [assetForm, setAssetForm] = useState(false);
  const [asset, setAsset] = useState({ asset_reference: "", asset_type: "parking", area: "", subtype_code:"" });
  const [revision, setRevision] = useState("");
  const [draftId, setDraftId] = useState<string | null>(null);
  const [measurements, setMeasurements] = useState<Record<string, string>>({});
  const [reconciled, setReconciled] = useState(false);
  const [source, setSource] = useState("");

  useEffect(() => {
    let current = true;
    void Promise.all([inventory.unitFeatures(projectId, unit.id), inventory.unitDocuments(projectId, unit.id)])
      .then(([f, d]) => { if (current) { setFeatures(f); setDocuments(d); setLoaded(true); } })
      .catch((caught) => { if (current) setError(caught instanceof ApiError ? caught.message : "Could not load features and documents."); });
    return () => { current = false; };
  }, [projectId, unit.id]);

  const save = async (action: () => Promise<unknown>) => {
    setBusy(true); setError(null);
    try {
      await action();
      const [f, d] = await Promise.all([inventory.unitFeatures(projectId, unit.id), inventory.unitDocuments(projectId, unit.id)]);
      setFeatures(f); setDocuments(d); setLoaded(true);
      await onChanged();
    } catch (caught) { setError(caught instanceof ApiError ? caught.message : "Could not save the physical record."); }
    finally { setBusy(false); }
  };

  const startMeasurement = (draft?: AreaSchedule) => {
    setDraftId(draft?.id ?? null); setRevision(draft?.revision_code ?? "");
    setSource(draft?.source ?? ""); setReconciled(draft?.reconciled ?? false);
    setMeasurements(Object.fromEntries((draft?.lines ?? unit.area_lines).map(line => [line.area_type_id, line.raw_area])));
    setMeasurementBaseline(JSON.stringify([draft?.revision_code ?? "",draft?.source ?? "",draft?.reconciled ?? false,Object.fromEntries((draft?.lines ?? unit.area_lines).map(line=>[line.area_type_id,line.raw_area]))]));
    setMeasuring(true);
  };

  return <div className="stack">
    {error ? <Notice tone="error">{error}</Notice> : null}
    <section>
      <SectionHeader level={2} title="Physical measurements" actions={canWrite ? <Button small data-leaves-editor disabled={busy} onClick={() => startMeasurement()}>Edit measurements</Button> : undefined} />
      <KeyValueGrid columns={3}>
        {PHYSICAL_COMPONENTS.map(([key, title]) => {
          const lines = unit.area_lines.filter(line => line.physical_component === key);
          return <KeyValue key={key} label={title} value={lines.length === 1 ? `${lines[0].raw_area} ${lines[0].unit_of_measure}` : lines.length > 1 ? "Multiple measurements — review revision" : "Not measured"} />;
        })}
        <KeyValue label="Net area" value={unit.net_area == null ? "Incomplete measurement" : `${unit.net_area} ${unit.net_area_unit ?? ""}`} />
        <KeyValue label="Gross area" value={unit.gross_area === null ? "Incomplete measurement" : `${unit.gross_area} ${unit.gross_area_unit ?? ""}`} />
      </KeyValueGrid>
      <p className="subtle">Net area = total internal areas + balcony areas. Gross area = Net area + Roof Garden + Terrace + Front Garden + Porches. Parking and storage are excluded. These are unweighted physical totals.</p>
      {unit.gross_area_reason ? <Notice tone="info">{unit.gross_area_reason}</Notice> : null}
      {canWrite && schedules.some(s => s.status === "draft") ? <div className="button-row">{schedules.filter(s => s.status === "draft").map(s => <Button key={s.id} small data-leaves-editor disabled={busy} onClick={() => startMeasurement(s)}>Edit draft {s.revision_code}</Button>)}</div> : null}
      {schedules.length ? <ul className="chip-list">{schedules.map(schedule=><li className="chip" key={schedule.id}><span>{schedule.revision_code} · {schedule.status}</span>{canApprove && schedule.status === "draft" ? <Button small data-leaves-editor disabled={busy} onClick={()=>void save(()=>inventory.approveAreaSchedule(projectId,unit.id,schedule.id))}>Approve measurement {schedule.revision_code}</Button> : null}</li>)}</ul> : null}
      {measuring && areaTypes.some(t => !t.is_active && measurements[t.id] !== undefined) ? <Notice tone="warning">Retired area types are omitted from the saved draft. Record any replacement measurement using an active type.</Notice> : null}
      {measuring ? <PropertyForm onDiscard={()=>setMeasuring(false)} busy={busy} dirty={measurementBaseline !== JSON.stringify([revision,source,reconciled,measurements])} onSubmit={event => { event.preventDefault(); void save(async () => {
        const payload = { source: source || null, reconciled, values: Object.entries(measurements).filter(([,value]) => value !== "").filter(([id]) => areaTypes.some(t => t.id === id && t.is_active)).map(([area_type_id, raw_area]) => ({ area_type_id, raw_area })) };
        if (draftId) await inventory.updateAreaSchedule(projectId, unit.id, draftId, payload);
        else await inventory.createAreaSchedule(projectId, unit.id, { ...payload, revision_code: revision });
        setMeasuring(false);
      }); }}>
        <FormSection title={draftId ? `Edit ${revision}` : "New measured revision"} description="An approved revision is preserved. Save a draft, reconcile it against its source drawing, then have it approved. Enter zero for an area that does not apply; leave unknown measurements blank.">
          <FieldRow columns={3}>
            <Field label="Revision code"><input className="input" required maxLength={32} disabled={draftId !== null || busy} value={revision} onChange={e => setRevision(e.target.value)} /></Field>
            <Field label="Source drawing"><input className="input" maxLength={120} disabled={busy} value={source} onChange={e => setSource(e.target.value)} /></Field>
          </FieldRow>
          <FieldRow columns={3}>{areaTypes.filter(t => t.is_active || measurements[t.id] !== undefined).map(t => <Field key={t.id} label={`${t.label} (${t.unit_of_measure})`}><input className="input" inputMode="decimal" disabled={busy || !t.is_active} value={measurements[t.id] ?? ""} onChange={e => setMeasurements({ ...measurements, [t.id]: e.target.value })} /></Field>)}</FieldRow>
          {areaTypes.length === 0 ? <Notice tone="info">Configure the project area types from Inventory first.</Notice> : null}
          <label className="checkbox"><input type="checkbox" checked={reconciled} disabled={busy} onChange={e => setReconciled(e.target.checked)} /><span>Reconciled against the source drawing</span></label>
        </FormSection>
        <FormActions><Button type="submit" disabled={busy || areaTypes.length === 0}>Save draft</Button><Button disabled={busy} onClick={() => setMeasuring(false)}>Cancel</Button></FormActions>
      </PropertyForm> : null}
    </section>
    <section>
      <SectionHeader level={2} title="Additional features" actions={canWrite ? <Button small data-leaves-editor disabled={busy} onClick={()=>setFeatureEditing(!featureEditing)}>{featureEditing ? "Close editor" : "Edit additional features"}</Button> : undefined} />
      <p className="subtle">Descriptive features can be added freely. Priced attributes remain in the governed unit fields.</p>
      {!loaded ? <p>{error ? "Features unavailable." : "Loading features…"}</p> : features.length === 0 ? <p className="subtle">No additional features recorded.</p> : <ul className="chip-list">{features.map(f => <li key={f.id} className="chip"><span>{f.label}{f.is_active ? "" : " · retired"}</span>{canWrite && featureEditing && f.is_active ? <Button small disabled={busy} onClick={() => void save(() => inventory.retireUnitFeature(projectId, unit.id, f.id))}>Retire</Button> : null}</li>)}</ul>}
      {canWrite && featureEditing ? <PropertyForm onDiscard={()=>{setLabel("");setFeatureEditing(false);}} busy={busy} dirty={label !== ""} onSubmit={e => { e.preventDefault(); void save(async () => { await inventory.addUnitFeature(projectId, unit.id, { label }); setLabel(""); }); }}><Field label="New feature"><input className="input" required maxLength={200} disabled={busy} value={label} onChange={e => setLabel(e.target.value)} /></Field><FormActions><Button type="submit" disabled={busy}>Add feature</Button><Button disabled={busy} onClick={()=>{setLabel("");setFeatureEditing(false);}}>Cancel</Button></FormActions></PropertyForm> : null}
    </section>
    <section>
      <SectionHeader level={2} title="Plans and specifications" actions={canWrite ? <Button small data-leaves-editor disabled={busy} onClick={()=>setDocEditing(!docEditing)}>{docEditing ? "Close editor" : "Edit plans and specifications"}</Button> : undefined} />
      <p className="subtle">Link the unit plans and specifications in your document system. Access to the linked file is controlled there.</p>
      {!loaded ? <p>{error ? "Documents unavailable." : "Loading documents…"}</p> : documents.length === 0 ? <p className="subtle">No unit documents linked.</p> : <ul>{documents.map(d => <li key={d.id}><a href={d.url} target="_blank" rel="noopener noreferrer">{d.title}</a>{d.revision ? ` · ${d.revision}` : ""}{d.is_active ? "" : " · retired"}{canWrite && docEditing && d.is_active ? <Button small disabled={busy} onClick={() => void save(() => inventory.retireUnitDocument(projectId, unit.id, d.id))}>Retire</Button> : null}</li>)}</ul>}
      {canWrite && docEditing ? <PropertyForm onDiscard={()=>{setDoc({title:"",url:"",revision:""});setDocEditing(false);}} busy={busy} dirty={Object.values(doc).some(Boolean)} onSubmit={e => { e.preventDefault(); void save(async () => { await inventory.addUnitDocument(projectId, unit.id, { ...doc, revision: doc.revision || null }); setDoc({ title: "", url: "", revision: "" }); }); }}><FieldRow columns={3}>
        <Field label="Document title"><input className="input" required maxLength={200} disabled={busy} value={doc.title} onChange={e => setDoc({ ...doc, title: e.target.value })} /></Field>
        <Field label="Document URL"><input className="input" type="url" required maxLength={2000} disabled={busy} value={doc.url} onChange={e => setDoc({ ...doc, url: e.target.value })} /></Field>
        <Field label="Document revision"><input className="input" maxLength={64} disabled={busy} value={doc.revision} onChange={e => setDoc({ ...doc, revision: e.target.value })} /></Field>
      </FieldRow><FormActions><Button type="submit" disabled={busy}>Link document</Button><Button disabled={busy} onClick={()=>{setDoc({title:"",url:"",revision:""});setDocEditing(false);}}>Cancel</Button></FormActions></PropertyForm> : null}
    </section>
    <section>
      <SectionHeader level={2} title="Parking and storage" actions={canWrite ? <Button small data-leaves-editor disabled={busy} onClick={() => setAssetForm(!assetForm)}>{assetForm ? "Close editor" : "Edit parking and storage"}</Button> : undefined} />
      {canWrite && assetForm ? <PropertyForm onDiscard={()=>{setAsset({asset_reference:"",asset_type:"parking",area:"",subtype_code:""});setAssetForm(false);}} busy={busy} dirty={asset.asset_reference !== "" || asset.area !== "" || asset.subtype_code !== "" || asset.asset_type !== "parking"} onSubmit={e => { e.preventDefault(); void save(async () => { await inventory.createSubAsset(projectId, { ...asset, subtype_code:asset.subtype_code || null, area: asset.area || null, linked_unit_id: unit.id, floor_id: unit.floor_id, transfer_mode: "attached" }); setAssetForm(false); setAsset({ asset_reference: "", asset_type: "parking", area: "", subtype_code:"" }); }); }}>
        <FieldRow columns={3}><Field label="Asset reference"><input className="input" required maxLength={64} disabled={busy} value={asset.asset_reference} onChange={e => setAsset({ ...asset, asset_reference: e.target.value })} /></Field><Field label="Asset type"><select className="input" disabled={busy} value={asset.asset_type} onChange={e => setAsset({ ...asset, asset_type: e.target.value })}><option value="parking">Parking</option><option value="storage">Storage</option></select></Field><Field label="Parking / storage type"><select className="input" disabled={busy} value={asset.subtype_code} onChange={e=>setAsset({...asset,subtype_code:e.target.value})}><option value="">Not assigned</option>{options.filter(option=>option.category==="sub_asset_subtype" && option.is_active).map(option=><option key={option.id} value={option.code}>{option.label}</option>)}</select></Field><Field label="Area (optional)"><input className="input" inputMode="decimal" disabled={busy} value={asset.area} onChange={e => setAsset({ ...asset, area: e.target.value })} /></Field></FieldRow><FormActions><Button type="submit" disabled={busy}>Attach asset</Button><Button disabled={busy} onClick={()=>{setAsset({asset_reference:"",asset_type:"parking",area:"",subtype_code:""});setAssetForm(false);}}>Cancel</Button></FormActions>
      </PropertyForm> : null}
      {assets.filter(a => a.is_active && ["parking", "storage"].includes(a.asset_type)).map(a => <div key={a.id} className="button-row"><span>{a.asset_reference} · {a.asset_type}{a.subtype_code ? ` · ${options.find(option=>option.category==="sub_asset_subtype" && option.code===a.subtype_code)?.label ?? a.subtype_code}` : ""}</span>{canWrite && assetForm ? <Button small disabled={busy} onClick={() => void save(() => inventory.updateSubAsset(projectId, a.id, { linked_unit_id: null }))}>Detach</Button> : null}</div>)}
      {assets.filter(a=>a.is_active && ["parking","storage"].includes(a.asset_type)).length===0 ? <p className="subtle">No parking or storage attached.</p> : null}
    </section>
  </div>;
}


/** Preserve a section draft when navigating away or while a save is in flight. */
function PropertyForm({dirty,busy,onDiscard,children,...props}: ComponentProps<"form"> & {dirty:boolean;busy:boolean;onDiscard?:()=>void}) {
  const form=useRef<HTMLFormElement>(null);
  return <form ref={form} {...props}><UnsavedChangesGuard form={form} dirty={dirty} busy={busy} onDiscard={onDiscard} />{children}</form>;
}
