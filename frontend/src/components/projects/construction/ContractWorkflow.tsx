"use client";
import * as ui from "@/components/ui";
import { useState } from "react";
import { ApiError, construction } from "@/lib/api";
import type { ContractDetail } from "@/lib/api";
import { Button, ButtonRow, Card, Disclosure, DraftBoundary, RecordPage, Field, FieldRow, FormDialog, KeyValue, KeyValueGrid, MoneyInput, Notice, RateInput } from "@/components/ui";
import { eventTime, fractionFromPercent, percentInput } from "@/lib/format";

type HeaderProps = { detail?: ContractDetail; currencyId: string; currencyCode: string | null; busy: boolean; failure: Error | null; unavailable?: boolean; onSubmit: (body: Record<string, unknown>) => void; onCancel: () => void };
function fieldError(failure: Error | null, field: string) { return failure instanceof ApiError ? failure.fieldErrors.filter(item => item.path.includes(field)).map(item => item.message).join(" ") || undefined : undefined; }

export function ContractHeaderEditor({ detail, currencyId, currencyCode, busy, failure, unavailable = false, onSubmit, onCancel }: HeaderProps) {
  const [form, setForm] = useState({ contract_number: detail?.contract_number ?? "", contract_type: detail?.contract_type ?? "works", vendor_name: detail?.vendor_name ?? "", original_contract_value_ex_tax: detail?.original_contract_value_ex_tax ?? "", advance_entitlement_amount: detail?.advance_entitlement_amount ?? "0.00", retention: percentInput(detail?.retention_rate_fraction ?? "0.000000"), tax: percentInput(detail?.tax_rate_fraction), vendor_registration_reference: detail?.vendor_registration_reference ?? "", vendor_tax_reference: detail?.vendor_tax_reference ?? "", vendor_contact_reference: detail?.vendor_contact_reference ?? "", payment_terms: detail?.payment_terms ?? "", planned_start_date: detail?.planned_start_date ?? "", planned_completion_date: detail?.planned_completion_date ?? "", notes: detail?.notes ?? "" });
  const [signedReference, setSignedReference] = useState("");
  const [initialForm] = useState(form);
  const change = (key: keyof typeof form, value: string) => setForm(current => ({ ...current, [key]: value }));
  function submit() {
    const { retention, tax, ...terms } = form;
    onSubmit({ ...terms, ...(!detail ? { signed_contract: true, signed_reference: signedReference } : {}), currency_id: currencyId, contract_number: form.contract_number.trim(), vendor_name: form.vendor_name.trim(), retention_rate_fraction: fractionFromPercent(retention), tax_rate_fraction: tax.trim() ? fractionFromPercent(tax) : null, planned_start_date: form.planned_start_date || null, planned_completion_date: form.planned_completion_date || null });
  }
  return <RecordPage title={detail ? "Edit draft terms" : "Add signed contract"} onClose={onCancel}>
    <DraftBoundary dirty={JSON.stringify(form) !== JSON.stringify(initialForm) || !!signedReference} busy={busy}>
    <form className="stack" onSubmit={event => { event.preventDefault(); if (!busy && !unavailable) submit(); }}>
    {failure ? <Notice tone="error">{failure.message}</Notice> : null}
    <p>{detail ? "Update these draft terms, then activate the signed agreement from Contract details." : "Enter the agreement already signed with your main contractor or subcontractor. Saving activates it immediately; no budget is needed."}</p>
    {!detail ? <Field label="Signed contract document reference"><input className="input" required maxLength={500} value={signedReference} onChange={e => setSignedReference(e.target.value)} /></Field> : null}
    <FieldRow><Field label="Contract reference" error={fieldError(failure, "contract_number")}><input className="input" required maxLength={64} value={form.contract_number} onChange={e => change("contract_number", e.target.value)} /></Field><Field label="Contract type"><select className="input" value={form.contract_type} onChange={e => change("contract_type", e.target.value)}>{[["works", "Works"], ["consultancy", "Consultancy"], ["supply", "Supply"], ["purchase_order", "Purchase order"], ["other", "Other"]].map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></Field></FieldRow>
    <Field label="Main contractor / subcontractor name" error={fieldError(failure, "vendor_name")}><input className="input" required maxLength={200} value={form.vendor_name} onChange={e => change("vendor_name", e.target.value)} /></Field>
    <Field label="Contract value excluding tax" error={fieldError(failure, "original_contract_value_ex_tax")}><MoneyInput code={currencyCode} required value={form.original_contract_value_ex_tax} onChange={v => change("original_contract_value_ex_tax", v)} /></Field>
    <Field label="Advance entitlement" hint="An entitlement, not cash paid." error={fieldError(failure, "advance_entitlement_amount")}><MoneyInput code={currencyCode} required value={form.advance_entitlement_amount} onChange={v => change("advance_entitlement_amount", v)} /></Field>
    <FieldRow><Field label="Retention percentage" error={fieldError(failure, "retention_rate_fraction")}><RateInput required value={form.retention} onChange={v => change("retention", v)} /></Field><Field label="Tax percentage" optional hint="Enter the agreed tax rate to show the remaining balance including tax. Enter zero for no tax; blank leaves that balance unavailable." error={fieldError(failure, "tax_rate_fraction")}><RateInput value={form.tax} onChange={v => change("tax", v)} /></Field></FieldRow>
    <Disclosure title="Additional contract details">
    <FieldRow><Field label="Planned start" optional><input className="input" type="date" value={form.planned_start_date} onChange={e => change("planned_start_date", e.target.value)} /></Field><Field label="Planned completion" optional><input className="input" type="date" min={form.planned_start_date || undefined} value={form.planned_completion_date} onChange={e => change("planned_completion_date", e.target.value)} /></Field></FieldRow>
    {([["vendor_registration_reference", "Vendor registration reference", 120], ["vendor_tax_reference", "Vendor tax reference", 120], ["vendor_contact_reference", "Vendor contact reference", 200], ["payment_terms", "Payment terms", 500]] as const).map(([key, label, max]) => <Field key={key} label={label} optional error={fieldError(failure, key)}><input className="input" maxLength={max} value={form[key]} onChange={e => change(key, e.target.value)} /></Field>)}
    <Field label="Notes" optional error={fieldError(failure, "notes")}><textarea className="input" maxLength={2000} value={form.notes} onChange={e => change("notes", e.target.value)} /></Field>
    </Disclosure>
    <Button type="submit" variant="primary" disabled={busy || unavailable || !currencyId}>{busy ? "Saving…" : detail ? "Save draft" : "Save and activate"}</Button>
    </form></DraftBoundary>
  </RecordPage>;
}

const labels = { signed: "Activate signed contract", cancel: "Cancel uncommitted contract", complete: "Complete contract", terminate: "Terminate contract" };
type Action = keyof typeof labels;
type Editor = { kind: "header" } | { kind: Action };
function ContractDecision({ action, busy, failure, unavailable = false, onSubmit, onCancel }: { action: Action; busy: boolean; failure: Error | null; unavailable?: boolean; onSubmit: (body: Record<string, unknown>) => void; onCancel: () => void }) {
  const [reason, setReason] = useState("");
  const needsReason = action === "cancel" || action === "terminate" || action === "signed";
  return <FormDialog title={labels[action]} confirmLabel={labels[action]} busy={busy} disabled={unavailable || (needsReason && !reason.trim())} onSubmit={() => onSubmit({ reason: reason.trim() })} onCancel={onCancel}>
    {failure ? <Notice tone="error">{failure.message}</Notice> : null}
    <p>{action === "signed" ? "Confirm this agreement has already been signed and enter its document reference. It becomes active immediately without a budget or another approval." : action === "cancel" ? "Keep the uncommitted record and its lines as cancelled history. Enter why it is being abandoned. This action cannot cancel a live commitment." : "Record the end of this contract. Its financial commitment remains unchanged; reducing an obligation requires an approved variation."}</p>
    {needsReason ? <Field label={action === "signed" ? "Signed contract document reference" : "Reason"} error={fieldError(failure, "reason")}><textarea className="input" required maxLength={1000} value={reason} onChange={e => setReason(e.target.value)} /></Field> : null}
  </FormDialog>;
}

export function ContractWorkflow({ projectId, detail, reading, unavailable, onChanged, onRefresh }: { projectId: string; detail: ContractDetail; reading: boolean; unavailable: boolean; onChanged: () => Promise<void>; onRefresh: () => Promise<void> }) {
  const [editor, setEditor] = useState<Editor | null>(null);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<Error | null>(null);
  // The barrel's hook, or a no-op where a test harness stands the barrel in.
  const { toast } = typeof ui.useToast === "function" ? ui.useToast() : { toast: () => {} };
  const setNotice = (text: string | null) => { if (text) toast({ title: text }); };
  const begin = (next: Editor) => { setFailure(null); setNotice(null); setEditor(next); };
  async function save(body: Record<string, unknown>) {
    if (!editor || busy || reading || unavailable) return;
    setBusy(true); setFailure(null);
    try {
      if (editor.kind === "header") await construction.updateConstructionContract(projectId, detail.id, body);
      else if (editor.kind === "signed") await construction.registerSignedContract(projectId, detail.id, String(body.reason));
      else if (editor.kind === "cancel") await construction.cancelContract(projectId, detail.id, String(body.reason));
      else if (editor.kind === "complete") await construction.completeContract(projectId, detail.id);
      else await construction.terminateContract(projectId, detail.id, String(body.reason));
      setEditor(null); setNotice("Contract saved. The current record is being refreshed.");
      await onChanged();
    } catch (caught) {
      setFailure(caught instanceof Error ? caught : new Error("The contract could not be saved."));
      if (caught instanceof ApiError && [403, 409].includes(caught.status)) await onRefresh();
    } finally { setBusy(false); }
  }
  const workflow = detail.workflow;
  const editorBlocker = unavailable ? "The contract could not be refreshed. Cancel this form, then refresh before saving." : !editor ? null : editor.kind === "header" ? workflow.editing_blocker : ({ signed: workflow.signed_registration_blocker, cancel: workflow.cancellation_blocker, complete: workflow.completion_blocker, terminate: workflow.termination_blocker })[editor.kind];
  const actions: [Action, string | null][] = detail.status === "draft" ? [["signed", workflow.signed_registration_blocker], ["cancel", workflow.cancellation_blocker]] : detail.status === "submitted" ? [["signed", workflow.signed_registration_blocker], ["cancel", workflow.cancellation_blocker]] : detail.status === "active" ? [["complete", workflow.completion_blocker], ["terminate", workflow.termination_blocker]] : [];
  return <div className="stack">
    {detail.status === "draft" || detail.status === "submitted" || detail.status === "cancelled" ? <Notice tone="info">Activate the signed agreement using its total contract price. No contract lines or budget are required.</Notice> : <Notice tone="info">This contract carries a standing commitment. Completion or termination does not reduce the money committed.</Notice>}
    <ButtonRow>{!workflow.editing_blocker ? <><Button disabled={unavailable || busy || reading} onClick={() => begin({ kind: "header" })}>Edit draft terms</Button></> : <p>{workflow.editing_blocker}</p>}</ButtonRow>
    {actions.map(([action, blocker]) => <div key={action}><Button disabled={unavailable || busy || reading || !!blocker} onClick={() => begin({ kind: action })}>{labels[action]}</Button>{blocker ? <p className="footnote">{blocker}</p> : null}</div>)}
    <Card title="Contract history"><KeyValueGrid>{([["Created", detail.created_at], ["Submitted", detail.submitted_at], ["Activated", detail.activated_at], ["Completed", detail.completed_at], ["Terminated", detail.terminated_at], ["Cancelled", detail.cancelled_at]] as const).map(([label, stamp]) => <KeyValue key={label} label={label} value={stamp ? eventTime(stamp) : "—"} />)}</KeyValueGrid>{detail.cancellation_reason ? <p>Cancellation: {detail.cancellation_reason}</p> : null}{detail.termination_reason ? <p>Termination: {detail.termination_reason}</p> : null}</Card>
    {editor?.kind === "header" ? <ContractHeaderEditor detail={detail} currencyId={detail.currency_id} currencyCode={detail.currency_code} busy={busy || reading} unavailable={!!editorBlocker} failure={failure ?? (editorBlocker ? new Error(editorBlocker) : null)} onSubmit={body => void save(body)} onCancel={() => setEditor(null)} /> : editor ? <ContractDecision action={editor.kind} busy={busy || reading} unavailable={!!editorBlocker} failure={failure ?? (editorBlocker ? new Error(editorBlocker) : null)} onSubmit={body => void save(body)} onCancel={() => setEditor(null)} /> : null}
  </div>;
}
