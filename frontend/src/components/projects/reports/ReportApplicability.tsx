"use client";

import { useState } from "react";
import { useAnswer } from "@/lib/answer";
import { siteReports, type SiteReport, type SiteReportFields } from "@/lib/api/siteReports";
import { Button, ButtonRow, Field, Loading, Notice, Segmented } from "@/components/ui";

export function ReportApplicability({ projectId, row, form, onChange }: { projectId: string; row?: SiteReport; form: SiteReportFields; onChange: (fields: SiteReportFields) => void }) {
  const answer = useAnswer(true, () => siteReports.targets(projectId), [projectId]);
  const [scope, setScope] = useState(form.building_id ? "building" : "units");
  const charter = form.kind === "client_charter";
  const selected = form.unit_ids ?? [];
  if (answer.status === "loading") return <Loading label="Loading buildings and units…" />;
  if (answer.status === "denied") return <Notice tone="warning">Building and unit selections require whole-project Design access.</Notice>;
  if (answer.status === "failed") return <Notice tone="error">{answer.message} <Button onClick={answer.retry}>Retry selections</Button></Notice>;
  if (answer.status !== "ready") return null;
  const labelOf = (id: string) => answer.data.units.find(unit => unit.id === id)?.label ?? row?.unit_labels?.[row.unit_ids?.indexOf(id) ?? -1] ?? id;
  const buildings = [...answer.data.buildings];
  if (row?.building_id && !buildings.some(b => b.id === row.building_id)) buildings.push({ id: row.building_id, label: (row.building_label ?? "Retained building") + " (retained)" });
  const units = [...answer.data.units];
  for (const id of selected) if (!units.some(u => u.id === id)) units.push({ id, label: labelOf(id) + " (retained)", building_id: "" });
  return <div className="stack">
    {!charter ? <Segmented label="Certificate applies to" value={scope} options={[{ value: "building", label: "Whole building" }, { value: "units", label: "Selected units" }]} onChange={value => { setScope(value); onChange({ ...form, building_id: null, unit_ids: [] }); }} /> : null}
    {!charter && scope === "building" ? <Field label="Building"><select className="input" required value={form.building_id ?? ""} onChange={event => onChange({ ...form, building_id: event.target.value || null, unit_ids: [] })}><option value="">Choose a building</option>{buildings.map(b => <option key={b.id} value={b.id}>{b.label}</option>)}</select></Field> : <>
      <Field label={charter ? "Unit" : "Add unit"} hint={!units.length ? "Add active units in Inventory before linking this document." : undefined}><select className="input" required={charter || !selected.length} value={charter ? selected[0] ?? "" : ""} onChange={event => { if (event.target.value) onChange({ ...form, building_id: null, unit_ids: charter ? [event.target.value] : [...selected, event.target.value] }); }}><option value="">Choose a unit</option>{units.filter(unit => charter || !selected.includes(unit.id)).map(unit => <option key={unit.id} value={unit.id}>{unit.label}</option>)}</select></Field>
      {!charter && selected.length ? <ButtonRow>{selected.map(id => <Button key={id} variant="quiet" aria-label={"Remove unit " + labelOf(id)} onClick={() => onChange({ ...form, unit_ids: selected.filter(value => value !== id) })}>{labelOf(id)} ×</Button>)}</ButtonRow> : null}
    </>}
  </div>;
}
