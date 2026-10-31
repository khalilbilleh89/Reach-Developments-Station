"use client";

import { useState } from "react";
import { ApiError } from "@/lib/api";
import { operations } from "@/lib/api/operations";
import type { OperationBuyer, OperationsData, ProgressDraft, PurchasePurpose } from "@/lib/api/operations";
import { Button, DraftBoundary, Field, FieldRow, FormActions, FormSection, Notice, RecordPage, Segmented, StatusDot } from "@/components/ui";
import { businessDate } from "@/lib/format";
import { DeleteRecordButton } from "../DeleteRecordButton";

const PURPOSES = [{value: "", label: "Not recorded"}, {value: "investment_only", label: "Investment Only"}, {value: "golden_visa", label: "Golden Visa"}];
const STATUSES = [{value: "", label: "Not recorded"}, {value: "yes", label: "Yes"}, {value: "no", label: "No"}];

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
  const savedPurpose = PURPOSES.find(option => option.value === (buyer.purpose ?? ""))!.label;
  return <RecordPage title={buyer.name} subtitle={`${buyer.number} · Operations`} onClose={onClose}
    strip={{
      lead: {label: "Applicable stages complete", value: `${buyer.completed_count} of ${buyer.applicable_count}`},
      items: [
        {label: "Purpose of Purchase", value: savedPurpose, tone: buyer.purpose ? undefined : "muted"},
        {label: "Next step", value: buyer.next_stage ?? (buyer.applicable_count ? "Applicable stages complete" : "No applicable stages")},
        {label: "Purchases", value: buyer.purchases.length ? buyer.purchases.map(purchase => purchase.number).join(", ") : "None current", tone: buyer.purchases.length ? undefined : "muted"},
      ],
    }}
    next={!buyer.purpose ? {text: "Record the purchase purpose to decide whether the Golden Visa stages apply."} : buyer.next_stage ? {text: `Next stage: ${buyer.next_stage}.`} : undefined}
    more={data.can_edit && buyer.version > 0 && !dirty ? <DeleteRecordButton label="manual progress" recordName={buyer.name} description="Clears manually entered milestones and purchase purpose. The buyer, purchases, linked Sales signatures and audit evidence are retained." onDelete={value => operations.deleteProgress(projectId, buyer.id, buyer.version, value)} onDeleted={onChanged} /> : undefined}>
    <DraftBoundary dirty={dirty} busy={busy}>
      <form className="stack" onSubmit={async event => {
        event.preventDefault(); setBusy(true); setError(null);
        const progress = Object.values(updates).filter(row => purpose === "golden_visa" || data.stages.find(stage => stage.id === row.stage_id)?.section !== "golden_visa");
        try { await operations.saveBuyer(projectId, buyer.id, buyer.version, data.pipeline_version, purpose, progress, reason); await onChanged(); }
        catch (caught) { setError(caught instanceof ApiError ? caught.message : "Could not save buyer progress."); }
        finally { setBusy(false); }
      }}>
        {error ? <Notice tone="error">{error}</Notice> : null}
        <Field label="Purpose of Purchase">{data.can_edit ? <Segmented label="Purpose of Purchase" value={purpose ?? ""} options={PURPOSES} onChange={value => setPurpose((value || null) as PurchasePurpose)} /> : <span>{savedPurpose}</span>}</Field>
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
                <Field label={`${stage.label} status`}>{editable ? <Segmented label={`${stage.label} status`} value={value.completed === null ? "" : value.completed ? "yes" : "no"} options={STATUSES} onChange={next => change(stage.id, {completed: next === "" ? null : next === "yes", ...(next !== "yes" ? {completed_date: null} : {})})} /> : <StatusDot tone={value.completed === true ? "success" : "neutral"}>{value.completed === null ? "Not recorded" : value.completed ? "Yes" : "No"}</StatusDot>}</Field>
                <Field label={`${stage.label} date`} optional hint={value.completed === true && !value.completed_date ? "Yes is recorded; the date is still missing." : undefined}><input className="input" type="date" disabled={!editable || value.completed !== true} value={value.completed_date ?? ""} onChange={event => change(stage.id, {completed_date: event.target.value || null})} /></Field>
              </FieldRow>
            </div>;
          })}
        </FormSection>)}
        {data.can_edit ? <>
          <Field label="Reason for update"><input className="input" required maxLength={1000} value={reason} onChange={event => setReason(event.target.value)} /></Field>
          <FormActions><Button type="submit" variant="primary" disabled={busy || !dirty}>{busy ? "Saving…" : "Save buyer progress"}</Button><Button data-leaves-editor onClick={onClose}>Cancel</Button></FormActions>
        </> : null}
      </form>
    </DraftBoundary>
  </RecordPage>;
}
