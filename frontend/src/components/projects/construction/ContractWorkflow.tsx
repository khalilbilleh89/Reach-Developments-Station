"use client";
import { useState } from "react";
import Link from "next/link";
import { projectHref } from "@/components/shell/navigation";
import { ApiError, construction } from "@/lib/api";
import type { ContractDetail, ContractLine, CostCode } from "@/lib/api";
import { Button, ButtonRow, Card, Field, FieldRow, FormDialog, KeyValue, KeyValueGrid, MoneyInput, Notice, RateInput, TableScroll } from "@/components/ui";
import { eventTime, fractionFromPercent, money, percentInput } from "@/lib/format";

type HeaderProps = { detail?: ContractDetail; currencyId: string; currencyCode: string | null; busy: boolean; failure: Error | null; unavailable?: boolean; onSubmit: (body: Record<string, unknown>) => void; onCancel: () => void };
function fieldError(failure: Error | null, field: string) { return failure instanceof ApiError ? failure.fieldErrors.filter(item => item.path.includes(field)).map(item => item.message).join(" ") || undefined : undefined; }

export function ContractHeaderEditor({ detail, currencyId, currencyCode, busy, failure, unavailable = false, onSubmit, onCancel }: HeaderProps) {
  const [form, setForm] = useState({ contract_number: detail?.contract_number ?? "", contract_type: detail?.contract_type ?? "works", vendor_name: detail?.vendor_name ?? "", original_contract_value_ex_tax: detail?.original_contract_value_ex_tax ?? "", advance_entitlement_amount: detail?.advance_entitlement_amount ?? "0.00", retention: percentInput(detail?.retention_rate_fraction ?? "0.000000"), tax: percentInput(detail?.tax_rate_fraction), vendor_registration_reference: detail?.vendor_registration_reference ?? "", vendor_tax_reference: detail?.vendor_tax_reference ?? "", vendor_contact_reference: detail?.vendor_contact_reference ?? "", payment_terms: detail?.payment_terms ?? "", planned_start_date: detail?.planned_start_date ?? "", planned_completion_date: detail?.planned_completion_date ?? "", notes: detail?.notes ?? "" });
  const change = (key: keyof typeof form, value: string) => setForm(current => ({ ...current, [key]: value }));
  function submit() {
    const { retention, tax, ...terms } = form;
    onSubmit({ ...terms, currency_id: currencyId, contract_number: form.contract_number.trim(), vendor_name: form.vendor_name.trim(), retention_rate_fraction: fractionFromPercent(retention), tax_rate_fraction: tax.trim() ? fractionFromPercent(tax) : null, planned_start_date: form.planned_start_date || null, planned_completion_date: form.planned_completion_date || null });
  }
  return <FormDialog title={detail ? "Edit draft terms" : "Create contract draft"} confirmLabel="Save draft" busy={busy} disabled={unavailable || !currencyId || !form.contract_number.trim() || !form.vendor_name.trim()} onSubmit={submit} onCancel={onCancel}>
    {failure ? <Notice tone="error">{failure.message}</Notice> : null}
    <p>Draft terms do not commit money. Allocate the exact value to cost-code lines, then submit for independent authorization.</p>
    <FieldRow><Field label="Contract reference" error={fieldError(failure, "contract_number")}><input className="input" required maxLength={64} value={form.contract_number} onChange={e => change("contract_number", e.target.value)} /></Field><Field label="Contract type"><select className="input" value={form.contract_type} onChange={e => change("contract_type", e.target.value)}>{[["works", "Works"], ["consultancy", "Consultancy"], ["supply", "Supply"], ["purchase_order", "Purchase order"], ["other", "Other"]].map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></Field></FieldRow>
    <Field label="Vendor name" error={fieldError(failure, "vendor_name")}><input className="input" required maxLength={200} value={form.vendor_name} onChange={e => change("vendor_name", e.target.value)} /></Field>
    <Field label="Contract value excluding tax" error={fieldError(failure, "original_contract_value_ex_tax")}><MoneyInput code={currencyCode} required value={form.original_contract_value_ex_tax} onChange={v => change("original_contract_value_ex_tax", v)} /></Field>
    <Field label="Advance entitlement" hint="An entitlement, not cash paid." error={fieldError(failure, "advance_entitlement_amount")}><MoneyInput code={currencyCode} required value={form.advance_entitlement_amount} onChange={v => change("advance_entitlement_amount", v)} /></Field>
    <FieldRow><Field label="Retention percentage" error={fieldError(failure, "retention_rate_fraction")}><RateInput required value={form.retention} onChange={v => change("retention", v)} /></Field><Field label="Tax percentage" optional hint="Leave blank when not stated; enter zero only when explicitly zero-rated." error={fieldError(failure, "tax_rate_fraction")}><RateInput value={form.tax} onChange={v => change("tax", v)} /></Field></FieldRow>
    <FieldRow><Field label="Planned start" optional><input className="input" type="date" value={form.planned_start_date} onChange={e => change("planned_start_date", e.target.value)} /></Field><Field label="Planned completion" optional><input className="input" type="date" min={form.planned_start_date || undefined} value={form.planned_completion_date} onChange={e => change("planned_completion_date", e.target.value)} /></Field></FieldRow>
    {([["vendor_registration_reference", "Vendor registration reference", 120], ["vendor_tax_reference", "Vendor tax reference", 120], ["vendor_contact_reference", "Vendor contact reference", 200], ["payment_terms", "Payment terms", 500]] as const).map(([key, label, max]) => <Field key={key} label={label} optional error={fieldError(failure, key)}><input className="input" maxLength={max} value={form[key]} onChange={e => change(key, e.target.value)} /></Field>)}
    <Field label="Notes" optional error={fieldError(failure, "notes")}><textarea className="input" maxLength={2000} value={form.notes} onChange={e => change("notes", e.target.value)} /></Field>
  </FormDialog>;
}

function ContractLineEditor({ detail, line, codes, busy, failure, unavailable = false, onSubmit, onCancel }: { detail: ContractDetail; line?: ContractLine; codes: CostCode[]; busy: boolean; failure: Error | null; unavailable?: boolean; onSubmit: (body: Record<string, unknown>) => void; onCancel: () => void }) {
  const [code, setCode] = useState(line?.cost_code_id ?? "");
  const [description, setDescription] = useState(line?.description ?? "");
  const [amount, setAmount] = useState(line?.original_amount_ex_tax ?? "");
  const [notes, setNotes] = useState(line?.notes ?? "");
  const sequence = line?.sequence ?? Math.max(0, ...detail.lines.map(item => item.sequence)) + 1;
  return <FormDialog title={line ? `Edit line ${sequence}` : "Add contract line"} confirmLabel="Save line" busy={busy} disabled={unavailable || !codes.some(item => item.id === code && item.is_active) || !description.trim()} onSubmit={() => onSubmit({ sequence, cost_code_id: code, description: description.trim(), original_amount_ex_tax: amount, notes })} onCancel={onCancel}>
    {failure ? <Notice tone="error">{failure.message}</Notice> : null}
    <p>Line {sequence}. To exclude a draft line, record zero; its entry stays visible. A retired cost code must be replaced with an active code before saving.</p>
    <Field label="Cost code" error={fieldError(failure, "cost_code_id")}><select className="input" required value={code} onChange={e => setCode(e.target.value)}><option value="">Choose cost code</option>{codes.filter(item => item.is_active || item.id === code).map(item => <option key={item.id} value={item.id} disabled={!item.is_active}>{item.code} · {item.name}{item.is_active ? "" : " · Retired"}</option>)}</select></Field>
    <Field label="Description" error={fieldError(failure, "description")}><input className="input" required maxLength={500} value={description} onChange={e => setDescription(e.target.value)} /></Field>
    <Field label="Line value excluding tax" error={fieldError(failure, "original_amount_ex_tax")}><MoneyInput required code={detail.currency_code} value={amount} onChange={setAmount} /></Field>
    <Field label="Notes" optional><textarea className="input" maxLength={2000} value={notes} onChange={e => setNotes(e.target.value)} /></Field>
  </FormDialog>;
}

const labels = { submit: "Submit for authorization", activate: "Authorize and activate", cancel: "Cancel uncommitted contract", complete: "Complete contract", terminate: "Terminate contract" };
type Action = keyof typeof labels;
type Editor = { kind: "header" } | { kind: "line"; line?: ContractLine } | { kind: Action };
function ContractDecision({ action, busy, failure, unavailable = false, onSubmit, onCancel }: { action: Action; busy: boolean; failure: Error | null; unavailable?: boolean; onSubmit: (body: Record<string, unknown>) => void; onCancel: () => void }) {
  const [reason, setReason] = useState("");
  const needsReason = action === "cancel" || action === "terminate";
  return <FormDialog title={labels[action]} confirmLabel={labels[action]} busy={busy} disabled={unavailable || (needsReason && !reason.trim())} onSubmit={() => onSubmit({ reason: reason.trim() })} onCancel={onCancel}>
    {failure ? <Notice tone="error">{failure.message}</Notice> : null}
    <p>{action === "submit" ? "Freeze the terms and lines for independent authorization. Correct submitted mistakes by cancelling this uncommitted record with a reason and preparing a new draft." : action === "activate" ? "Commit this contract against the active budget. The server rechecks independent authorization, exact line totals, currency and available budget before activation." : action === "cancel" ? "Keep the uncommitted record and its lines as cancelled history. Enter why it is being abandoned. This action cannot cancel a live commitment." : "Record the end of this contract. Its financial commitment remains unchanged; reducing an obligation requires an approved variation."}</p>
    {needsReason ? <Field label="Reason" error={fieldError(failure, "reason")}><textarea className="input" required maxLength={1000} value={reason} onChange={e => setReason(e.target.value)} /></Field> : null}
  </FormDialog>;
}

export function ContractWorkflow({ projectId, detail, codes, codesReady, reading, unavailable, onChanged, onRefresh }: { projectId: string; detail: ContractDetail; codes: CostCode[]; codesReady: boolean; reading: boolean; unavailable: boolean; onChanged: () => Promise<void>; onRefresh: () => Promise<void> }) {
  const [editor, setEditor] = useState<Editor | null>(null);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<Error | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const begin = (next: Editor) => { setFailure(null); setNotice(null); setEditor(next); };
  async function save(body: Record<string, unknown>) {
    if (!editor || busy || reading || unavailable) return;
    setBusy(true); setFailure(null);
    try {
      if (editor.kind === "header") await construction.updateConstructionContract(projectId, detail.id, body);
      else if (editor.kind === "line") await construction.writeContractLine(projectId, detail.id, body);
      else if (editor.kind === "submit") await construction.submitContract(projectId, detail.id);
      else if (editor.kind === "activate") await construction.activateContract(projectId, detail.id);
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
  const editorBlocker = unavailable ? "The contract could not be refreshed. Cancel this form, then refresh before saving." : !editor ? null : editor.kind === "header" || editor.kind === "line" ? workflow.editing_blocker : ({ submit: workflow.submission_blocker, activate: workflow.activation_blocker, cancel: workflow.cancellation_blocker, complete: workflow.completion_blocker, terminate: workflow.termination_blocker })[editor.kind];
  const actions: [Action, string | null][] = detail.status === "draft" ? [["submit", workflow.submission_blocker], ["cancel", workflow.cancellation_blocker]] : detail.status === "submitted" ? [["activate", workflow.activation_blocker], ["cancel", workflow.cancellation_blocker]] : detail.status === "active" ? [["complete", workflow.completion_blocker], ["terminate", workflow.termination_blocker]] : [];
  return <div className="stack">
    {notice ? <Notice tone="success">{notice}</Notice> : null}
    {detail.status === "draft" || detail.status === "submitted" || detail.status === "cancelled" ? <Notice tone="info">This contract has not become a financial commitment. Authorization and activation are one independent decision.</Notice> : <Notice tone="info">This contract carries a standing commitment. Completion or termination does not reduce the money committed.</Notice>}
    <KeyValueGrid><KeyValue label="Contract value excluding tax" value={money(detail.original_contract_value_ex_tax, detail.currency_code)} /><KeyValue label="Line total excluding tax" value={money(detail.line_total, detail.currency_code)} /></KeyValueGrid>
    <p><Link href={`${projectHref(projectId, "construction")}&constructionTab=budget`}>Open construction budget and cost codes</Link></p>
    {codesReady && !codes.some(code => code.is_active) ? <Notice tone="warning">No active cost codes are available. A preparer can add them in Budget before allocating contract lines.</Notice> : null}
    <ButtonRow>{!workflow.editing_blocker ? <><Button disabled={unavailable || busy || reading} onClick={() => begin({ kind: "header" })}>Edit draft terms</Button><Button disabled={unavailable || busy || reading || !codesReady} onClick={() => begin({ kind: "line" })}>Add contract line</Button></> : <p>{workflow.editing_blocker}</p>}</ButtonRow>
    {actions.map(([action, blocker]) => <div key={action}><Button disabled={unavailable || busy || reading || !!blocker} onClick={() => begin({ kind: action })}>{labels[action]}</Button>{blocker ? <p className="footnote">{blocker}</p> : null}</div>)}
    <Card title="Contract lines" description="Each line allocates original value; commitment and certification remain grouped by cost code in Position."><TableScroll label="Draft contract lines"><thead><tr><th scope="col">Line</th><th scope="col">Description / cost code</th><th scope="col">Value excluding tax</th><th scope="col">Action</th></tr></thead><tbody>{detail.lines.map(line => <tr key={line.id}><th scope="row">{line.sequence}</th><td>{line.description}<p>{line.cost_code}</p>{line.notes}</td><td>{money(line.original_amount_ex_tax, detail.currency_code)}</td><td>{!workflow.editing_blocker ? <Button disabled={unavailable || busy || reading || !codesReady} onClick={() => begin({ kind: "line", line })}>Edit line {line.sequence}</Button> : "Read-only"}</td></tr>)}</tbody></TableScroll>{!detail.lines.length ? <p>No lines yet. Add the cost-code allocation before submitting.</p> : null}</Card>
    <Card title="Contract history"><KeyValueGrid>{([["Created", detail.created_at], ["Submitted", detail.submitted_at], ["Activated", detail.activated_at], ["Completed", detail.completed_at], ["Terminated", detail.terminated_at], ["Cancelled", detail.cancelled_at]] as const).map(([label, stamp]) => <KeyValue key={label} label={label} value={stamp ? eventTime(stamp) : "—"} />)}</KeyValueGrid>{detail.cancellation_reason ? <p>Cancellation: {detail.cancellation_reason}</p> : null}{detail.termination_reason ? <p>Termination: {detail.termination_reason}</p> : null}</Card>
    {editor?.kind === "header" ? <ContractHeaderEditor detail={detail} currencyId={detail.currency_id} currencyCode={detail.currency_code} busy={busy || reading} unavailable={!!editorBlocker} failure={failure ?? (editorBlocker ? new Error(editorBlocker) : null)} onSubmit={body => void save(body)} onCancel={() => setEditor(null)} /> : editor?.kind === "line" ? <ContractLineEditor detail={detail} line={editor.line} codes={codes} busy={busy || reading} unavailable={!!editorBlocker} failure={failure ?? (editorBlocker ? new Error(editorBlocker) : null)} onSubmit={body => void save(body)} onCancel={() => setEditor(null)} /> : editor ? <ContractDecision action={editor.kind} busy={busy || reading} unavailable={!!editorBlocker} failure={failure ?? (editorBlocker ? new Error(editorBlocker) : null)} onSubmit={body => void save(body)} onCancel={() => setEditor(null)} /> : null}
  </div>;
}
