"use client";
import { useState } from "react";
import { construction } from "@/lib/api";
import type { Certificate, ConstructionInvoice, ContractDetail } from "@/lib/api";
import { hasAnyRole } from "@/lib/roles";
import { money, businessDate } from "@/lib/format";
import { Button, DraftBoundary, Field, FieldRow, MoneyInput, Notice, PromptDialog, RecordPage, RowMenu, TableScroll } from "@/components/ui";
import { DeleteRecordButton } from "../DeleteRecordButton";

type Props = { projectId: string; contract: ContractDetail; roles: Set<string>; certificates: Certificate[] | null; invoices: ConstructionInvoice[] | null; mode: "certificates" | "invoices"; unavailable: boolean; onChanged: () => Promise<void> };
export function ContractDocuments({ projectId, contract, roles, certificates, invoices, mode, unavailable, onChanged }: Props) {
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [prompt, setPrompt] = useState<{ title: string; run: (reason: string) => Promise<unknown> } | null>(null);
  const technical = hasAnyRole(roles, new Set(["finance", "project_manager", "design_engineering"]));
  const finance = hasAnyRole(roles, new Set(["finance"]));
  const checker = hasAnyRole(roles, new Set(["finance", "approver_cfo"]));
  const standing = ["active", "completed", "terminated"].includes(contract.status);
  async function act(run: () => Promise<unknown>) {
    if (busy || unavailable) return;
    setBusy(true); setError(null);
    try { await run(); setPrompt(null); await onChanged(); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Could not save this record."); }
    finally { setBusy(false); }
  }
  if (editing) return <DocumentEditor {...{ projectId, contract, certificates, mode, unavailable, onChanged }} onClose={() => setEditing(false)} />;
  return <div className="stack">
    {error ? <Notice tone="error">{error}</Notice> : null}
    {standing && (mode === "certificates" ? technical : finance) ? <Button variant="primary" disabled={busy || unavailable} onClick={() => setEditing(true)}>{mode === "certificates" ? "Add completion certificate" : "Add invoice"}</Button> : null}
    {!standing ? <Notice tone="info">Activate the signed contract on Contract & payments before adding records.</Notice> : null}
    <p>{mode === "certificates" ? "Enter the value of work completed this period. Retention is calculated from the contract rate. Submit the draft for certification by another authorized user. Certified work is a financial valuation; physical stage completion is recorded separately in Milestones." : "Record an advance invoice before its payment, or a progress invoice against a certified valuation. Another Finance or CFO user approves the invoice. Then record the actual payment on Contract & payments and select this invoice."}</p>
    {mode === "certificates" ? <>
      {certificates === null ? <Notice tone="warning">Certificates are unavailable. Refresh the contract.</Notice> : certificates.length === 0 ? <p>No certificates yet.</p> : <TableScroll label="Completion certificates"><thead><tr><th scope="col">Certificate / date</th><th scope="col">Work this period</th><th scope="col">Retention withheld</th><th scope="col">Retention released</th><th scope="col">Advance recovered</th><th scope="col">Other deductions</th><th scope="col">Tax</th><th scope="col">Net due</th><th scope="col">Status / actions</th></tr></thead><tbody>{certificates.map(row => <tr key={row.id}><th scope="row">{row.certificate_number}<p>{businessDate(row.certificate_date)}</p>{row.evidence_reference}</th><td>{money(row.current_work_value_ex_tax, contract.currency_code)}</td><td>{money(row.retention_held_amount, contract.currency_code)}</td><td>{money(row.retention_release_amount, contract.currency_code)}</td><td>{money(row.advance_recovery_amount, contract.currency_code)}</td><td>{money(row.other_deductions_amount, contract.currency_code)}</td><td>{money(row.tax_amount, contract.currency_code)}</td><td>{money(row.net_due, contract.currency_code)}</td><td>{row.status}<RowMenu label="More actions">
        {technical && row.status === "draft" ? <><Button disabled={busy || unavailable} onClick={() => void act(() => construction.submitCertificate(projectId, row.id))}>Submit for certification</Button><DeleteRecordButton label="draft certificate" recordName={row.certificate_number} description="Remove this draft valuation and its work amount. Audit evidence remains." onDelete={reason => construction.deleteDraftCertificate(projectId, row.id, reason)} onDeleted={onChanged} /></> : null}
        {technical && row.status === "submitted" ? <><Button disabled={busy || unavailable} onClick={() => void act(() => construction.certifyCertificate(projectId, row.id))}>Certify</Button><Button disabled={busy || unavailable} onClick={() => setPrompt({ title: "Reject certificate", run: reason => construction.rejectCertificate(projectId, row.id, reason) })}>Reject</Button></> : null}
        {technical && row.status === "certified" ? <Button disabled={busy || unavailable} onClick={() => setPrompt({ title: "Reverse certificate", run: reason => construction.reverseCertificate(projectId, row.id, reason) })}>Reverse</Button> : null}
      </RowMenu>{row.rejection_reason ?? row.reversal_reason}</td></tr>)}</tbody></TableScroll>}
    </> : <>
      {invoices === null ? <Notice tone="warning">Invoices are unavailable. Refresh the contract.</Notice> : invoices.length === 0 ? <p>No invoices yet.</p> : <TableScroll label="Invoices and outstanding balances"><thead><tr><th scope="col">Invoice / type</th><th scope="col">Due date</th><th scope="col">Amount including tax</th><th scope="col">Paid against invoice</th><th scope="col">Outstanding</th><th scope="col">Status / actions</th></tr></thead><tbody>{invoices.map(row => <tr key={row.id}><th scope="row">{row.invoice_number}<p>{row.invoice_type}</p></th><td>{businessDate(row.due_date)}</td><td>{money(row.net_payable, contract.currency_code)}</td><td>{money(row.allocated, contract.currency_code)}</td><td>{money(row.outstanding, contract.currency_code)}</td><td>{row.status}<RowMenu label="More actions">
        {checker && row.status === "recorded" ? <Button disabled={busy || unavailable} onClick={() => void act(() => construction.approveInvoice(projectId, row.id))}>Approve invoice</Button> : null}
        {finance && ["recorded", "approved"].includes(row.status) ? <Button disabled={busy || unavailable} onClick={() => setPrompt({ title: "Dispute invoice", run: reason => construction.disputeInvoice(projectId, row.id, reason) })}>Dispute</Button> : null}
        {finance && row.status === "disputed" ? <Button disabled={busy || unavailable} onClick={() => setPrompt({ title: "Resolve invoice dispute", run: reason => construction.resolveInvoice(projectId, row.id, reason) })}>Resolve dispute</Button> : null}
        {finance && row.status !== "voided" ? <DeleteRecordButton label="invoice" recordName={row.invoice_number} description="Void this invoice with a reason. Financial evidence is retained; paid invoices require payment reversal first." confirmLabel="Void invoice" onDelete={async reason => { await construction.voidInvoice(projectId, row.id, reason); }} onDeleted={onChanged} /> : null}
      </RowMenu>{row.dispute_reason ?? row.void_reason}</td></tr>)}</tbody></TableScroll>}
    </>}
    {prompt ? <PromptDialog title={prompt.title} label="Reason" description="The original record and audit history remain." busy={busy} error={error} onCancel={() => setPrompt(null)} onSubmit={reason => void act(() => prompt.run(reason))} /> : null}
  </div>;
}

function DocumentEditor({ projectId, contract, certificates, mode, unavailable, onChanged, onClose }: Pick<Props, "projectId" | "contract" | "certificates" | "mode" | "unavailable" | "onChanged"> & { onClose: () => void }) {
  const [form, setForm] = useState({ reference: "", date: "", start: "", end: "", due: "", amount: "", tax: "0.00", release: "0.00", recovery: "0.00", deductions: "0.00", evidence: "", notes: "", type: "progress", certificate: "", code: contract.cost_code_position[0]?.cost_code_id ?? "" });
  const [initial] = useState(form);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const certificate = mode === "certificates";
  const change = (key: keyof typeof form, value: string) => setForm(current => ({ ...current, [key]: value }));
  async function save() {
    if (busy || unavailable || saved) return;
    setBusy(true); setError(null);
    try {
      if (certificate) await construction.createCertificate(projectId, contract.id, { certificate_number: form.reference, certificate_date: form.date, period_start: form.start, period_end: form.end, current_work_value_ex_tax: form.amount, cost_code_id: contract.cost_code_position.length > 1 ? form.code : null, retention_release_amount: form.release, advance_recovery_amount: form.recovery, other_deductions_amount: form.deductions, tax_amount: form.tax, evidence_reference: form.evidence || null, notes: form.notes || null });
      else await construction.recordInvoice(projectId, contract.id, { invoice_number: form.reference, invoice_type: form.type, invoice_date: form.date, due_date: form.due || null, amount_ex_tax: form.amount, tax_amount: form.tax, certificate_id: form.type === "advance" ? null : form.certificate, accounting_reference: form.evidence || null, notes: form.notes || null });
      setSaved(true); onClose(); await onChanged();
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Could not save the document."); }
    finally { setBusy(false); }
  }
  return <RecordPage title={certificate ? "Add completion certificate" : "Add invoice"} subtitle={contract.contract_number + " · " + contract.vendor_name} onClose={onClose}><DraftBoundary dirty={!saved && JSON.stringify(form) !== JSON.stringify(initial)} busy={busy}><form className="stack" onSubmit={event => { event.preventDefault(); void save(); }}>
    {error ? <Notice tone="error">{error}</Notice> : null}
    <FieldRow><Field label="Reference"><input className="input" required maxLength={64} value={form.reference} onChange={e => change("reference", e.target.value)} /></Field><Field label="Document date"><input className="input" type="date" required value={form.date} onChange={e => change("date", e.target.value)} /></Field></FieldRow>
    {certificate ? <>
      <FieldRow><Field label="Period start"><input className="input" type="date" required value={form.start} onChange={e => change("start", e.target.value)} /></Field><Field label="Period end"><input className="input" type="date" required min={form.start || undefined} value={form.end} onChange={e => change("end", e.target.value)} /></Field></FieldRow>
      {contract.cost_code_position.length > 1 ? <Field label="Existing contract scope"><select className="input" required value={form.code} onChange={e => change("code", e.target.value)}>{contract.cost_code_position.map(row => <option key={row.cost_code_id} value={row.cost_code_id}>{row.cost_code_name}</option>)}</select></Field> : null}
      <p>Enter only new work in this period, not the cumulative total. Previously certified work: {money(contract.certified_to_date, contract.currency_code)}. Advance outstanding: {money(contract.advance_outstanding, contract.currency_code)}. Retention held: {money(contract.retention_outstanding, contract.currency_code)}.</p>
    </> : <>
      <Field label="Invoice type"><select className="input" value={form.type} onChange={e => change("type", e.target.value)}>{["progress", "advance", "retention_release", "final", "other"].map(type => <option key={type} value={type}>{type.replaceAll("_", " ")}</option>)}</select></Field>
      {form.type !== "advance" ? <Field label="Certified valuation"><select className="input" required value={form.certificate} onChange={e => change("certificate", e.target.value)}><option value="">Choose certificate</option>{certificates?.filter(row => row.status === "certified").map(row => <option key={row.id} value={row.id}>{row.certificate_number} · uninvoiced {money(row.uninvoiced_net_due, contract.currency_code)}</option>)}</select></Field> : <p>Advance invoices use the agreed advance entitlement. Paying an approved advance invoice makes that cash available for recovery on later certificates.</p>}
      <Field label="Due date" optional><input className="input" type="date" value={form.due} onChange={e => change("due", e.target.value)} /></Field>
    </>}
    <Field label={certificate ? "Work completed this period, excluding tax" : "Invoice amount excluding tax"} hint={certificate ? "Retention is calculated by the server using the contract rate." : "Enter the amount payable after certificate deductions, before tax."}><MoneyInput required code={contract.currency_code} value={form.amount} onChange={v => change("amount", v)} /></Field>
    {certificate ? <>{([["release", "Retention released"], ["recovery", "Advance recovery this period"], ["deductions", "Other deductions"]] as const).map(([key, label]) => <Field key={key} label={label}><MoneyInput required code={contract.currency_code} value={form[key]} onChange={v => change(key, v)} /></Field>)}</> : null}
    <Field label="Tax amount" hint="Use the document's tax amount. Zero is explicit; no sales VAT rate is assumed."><MoneyInput required code={contract.currency_code} value={form.tax} onChange={v => change("tax", v)} /></Field>
    <Field label={certificate ? "Certificate / completion evidence reference" : "Accounting / document reference"} optional={!certificate}><input className="input" required={certificate} maxLength={certificate ? 500 : 120} value={form.evidence} onChange={e => change("evidence", e.target.value)} /></Field>
    <Field label="Notes" optional><textarea className="input" maxLength={2000} value={form.notes} onChange={e => change("notes", e.target.value)} /></Field>
    <Button type="submit" variant="primary" disabled={busy || unavailable || saved}>{busy ? "Saving…" : certificate ? "Save draft certificate" : "Record invoice"}</Button>
  </form></DraftBoundary></RecordPage>;
}
