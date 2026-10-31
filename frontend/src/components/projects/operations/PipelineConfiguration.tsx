"use client";

import { useState } from "react";
import { ApiError } from "@/lib/api";
import { operations } from "@/lib/api/operations";
import type { OperationsData, OperationSection, StageDraft } from "@/lib/api/operations";
import { Button, DraftBoundary, Field, FieldRow, FormActions, Notice, RecordPage, Segmented, SubPanel } from "@/components/ui";
import { DeleteRecordButton } from "../DeleteRecordButton";

export function PipelineConfiguration({projectId, data, onClose, onChanged}: {
  projectId: string; data: OperationsData; onClose: () => void; onChanged: () => Promise<void>;
}) {
  const initial = data.stages.map(({id, label, section, is_active}) => ({id, label, section, is_active}));
  const [stages, setStages] = useState<StageDraft[]>(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dirty = JSON.stringify(stages) !== JSON.stringify(initial);
  const change = (index: number, patch: Partial<StageDraft>) => setStages(rows => rows.map((row, at) => at === index ? {...row, ...patch} : row));
  const move = (index: number, direction: number) => setStages(rows => {
    const result = [...rows];
    [result[index], result[index + direction]] = [result[index + direction], result[index]];
    return result;
  });
  return <RecordPage title="Operations pipeline configuration" subtitle="One sequence for this project. Existing buyer progress stays attached to its stage when you rename or reorder it." onClose={onClose}>
    <DraftBoundary dirty={dirty} busy={busy}>
      <form onSubmit={async event => {
        event.preventDefault(); setBusy(true); setError(null);
        try { await operations.savePipeline(projectId, data.pipeline_version, stages); await onChanged(); }
        catch (caught) { setError(caught instanceof ApiError ? caught.message : "Could not save the pipeline."); }
        finally { setBusy(false); }
      }} className="stack">
        {error ? <Notice tone="error">{error}</Notice> : null}
        <Notice tone="info">Added stages appear for every buyer. Retired stages keep their recorded evidence. Save your changes before deleting an existing stage.</Notice>
        {stages.map((stage, index) => <SubPanel key={stage.id ?? `new-${index}`}><div className="stack">
          <FieldRow>
            <Field label="Stage name"><input className="input" required maxLength={160} value={stage.label} onChange={event => change(index, {label: event.target.value})} /></Field>
            <Field label="Section"><Segmented<OperationSection> label={`Section for ${stage.label || "new stage"}`} value={stage.section} options={[{value: "property_purchase", label: "Property Purchase"}, {value: "golden_visa", label: "Golden Visa"}]} onChange={value => change(index, {section: value})} /></Field>
          </FieldRow>
          <Field label="Availability"><Segmented label={`Availability of ${stage.label || "new stage"}`} value={stage.is_active ? "active" : "retired"} options={[{value: "active", label: "Active"}, {value: "retired", label: "Retired — keep history"}]} onChange={value => change(index, {is_active: value === "active"})} /></Field>
          {data.stages.find(row => row.id === stage.id)?.source === "buyer_signed_spa" ? <p className="muted">Automatically follows buyer signatures in Sales when a current sale exists.</p> : null}
          <FormActions>
            <Button disabled={index === 0} onClick={() => move(index, -1)} aria-label={`Move ${stage.label || "new stage"} up`}>Move up</Button>
            <Button disabled={index === stages.length - 1} onClick={() => move(index, 1)} aria-label={`Move ${stage.label || "new stage"} down`}>Move down</Button>
            {stage.id === null ? <Button variant="danger" onClick={() => setStages(rows => rows.filter((_, at) => at !== index))}>Delete new stage</Button> : !dirty ? <DeleteRecordButton label="stage" recordName={stage.label} description="An unused stage is deleted. A stage with buyer entries is retired, retaining those entries and the audit history." onDelete={reason => operations.deleteStage(projectId, stage.id!, data.pipeline_version, reason)} onDeleted={onChanged} /> : null}
          </FormActions>
        </div></SubPanel>)}
        <FormActions>
          <Button disabled={stages.length >= 100} onClick={() => setStages(rows => [...rows, {id: null, label: "", section: "property_purchase", is_active: true}])}>Add stage</Button>
          <Button type="submit" variant="primary" disabled={busy || !dirty}>{busy ? "Saving…" : "Save pipeline"}</Button>
          <Button data-leaves-editor onClick={onClose}>Cancel</Button>
        </FormActions>
      </form>
    </DraftBoundary>
  </RecordPage>;
}
