"use client";

import { useState } from "react";
import { ApiError } from "@/lib/api";
import { operations } from "@/lib/api/operations";
import type { OperationBuyer, OperationsData, ProgressDraft, PurchasePurpose } from "@/lib/api/operations";
import { Button, DraftBoundary, Field, FieldRow, FormActions, FormSection, Notice, RecordPage } from "@/components/ui";
import { businessDate } from "@/lib/format";
import { DeleteRecordButton } from "../DeleteRecordButton";

export function BuyerOperations({projectId, buyer, data, onClose, onChanged}: {
  projectId: string; buyer: OperationBuyer; data: OperationsData; onClose: () => void; onChanged: () => Promise<void>;
}) {
  const [purpose, setPurpose] = useState<PurchasePurpose>(buyer.purpose);
  const [updates, setUpdates] = useState<Record<string, ProgressDraft>>({});
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dirty = purpose !== buyer.purpose || Object.keys(updates).length > 0;
  const change = (id: string, patch: Partial<ProgressDraft>) => setUpdates(current => {
    const original = buyer.milestones.find(row => row.stage_id === id)!;
    return {...current, [id]: {...(current[id] ?? {stage_id: id, completed: original.completed, completed_date: original.completed_date}), ...patch}};
  });
  return <RecordPage title={buyer.name} subtitle={`${buyer.number} · Operations`} onClose={onClose}>
    <DraftBoundary dirty={dirty} busy={busy}>
      <form className="stack" onSubmit={async event => {
        event.preventDefault(); setBusy(true); setError(null);
        const progress = Object.values(updates).filter(row => purpose === "golden_visa" || data.stages.find(stage => stage.id === row.stage_id)?.section !== "golden_visa");
        try { await operations.saveBuyer(projectId, buyer.id, buyer.version, data.pipeline_version, purpose, progress, reason); await onChanged(); }
        catch (caught) { setError(caught instanceof ApiError ? caught.message : "Could not save buyer progress."); }
        finally { setBusy(false); }
      }}>
        {error ? <Notice tone="error">{error}</Notice> : null}
        <Field label="Purpose of Purchase"><select disabled={!data.can_edit} value={purpose ?? ""} onChange={event => setPurpose((event.target.value || null) as PurchasePurpose)}><option value="">Not recorded</option><option value="investment_only">Investment Only</option><option value="golden_visa">Golden Visa</option></select></Field>
        {(["property_purchase", "golden_visa"] as const).map(section => <FormSection key={section} title={section === "property_purchase" ? "1. Property Purchase" : "2. Golden Visa"}>
          {section === "golden_visa" && purpose !== "golden_visa" ? <Notice tone="info">{purpose === null ? "Choose a purchase purpose to determine whether these stages apply." : "Not applicable to Investment Only. Previously recorded visa progress is retained."}</Notice> : null}
          {data.stages.filter(stage => stage.section === section).map(stage => {
            const original = buyer.milestones.find(row => row.stage_id === stage.id)!;
            const value = updates[stage.id] ?? original;
            const linked = original.total_sales > 0;
            const editable = data.can_edit && stage.is_active && !linked && (section === "property_purchase" || purpose === "golden_visa");
            return <div className="stack" key={stage.id}>
              <h3>{stage.label}{!stage.is_active ? " · Retired" : ""}</h3>
              {linked ? <p>{original.signed_sales} of {original.total_sales} current purchases signed by the buyer. {original.completed_date ? businessDate(original.completed_date) : "Completion date not recorded."} Update the legal timeline in Sales.</p> : null}
              <FieldRow>
                <Field label={`${stage.label} status`}><select disabled={!editable} value={value.completed === null ? "" : value.completed ? "yes" : "no"} onChange={event => change(stage.id, {completed: event.target.value === "" ? null : event.target.value === "yes", ...(event.target.value !== "yes" ? {completed_date: null} : {})})}><option value="">Not recorded</option><option value="yes">Yes</option><option value="no">No</option></select></Field>
                <Field label={`${stage.label} date`} optional hint={value.completed === true && !value.completed_date ? "Yes is recorded; the date is still missing." : undefined}><input type="date" disabled={!editable || value.completed !== true} value={value.completed_date ?? ""} onChange={event => change(stage.id, {completed_date: event.target.value || null})} /></Field>
              </FieldRow>
            </div>;
          })}
        </FormSection>)}
        {data.can_edit ? <>
          <Field label="Reason for update"><input required maxLength={1000} value={reason} onChange={event => setReason(event.target.value)} /></Field>
          <FormActions><Button type="submit" variant="primary" disabled={busy || !dirty}>{busy ? "Saving…" : "Save buyer progress"}</Button><Button data-leaves-editor onClick={onClose}>Cancel</Button></FormActions>
          {buyer.version > 0 && !dirty ? <DeleteRecordButton label="manual progress" recordName={buyer.name} description="Clears manually entered milestones and purchase purpose. The buyer, purchases, linked Sales signatures and audit evidence are retained." onDelete={value => operations.deleteProgress(projectId, buyer.id, buyer.version, value)} onDeleted={onChanged} /> : null}
        </> : null}
      </form>
    </DraftBoundary>
  </RecordPage>;
}
