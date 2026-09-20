"use client";

import { useState } from "react";
import { construction } from "@/lib/api";
import type { ContractDetail, ConstructionPayment, Variation } from "@/lib/api";
import { hasAnyRole } from "@/lib/roles";
import { money, businessDate } from "@/lib/format";
import { Button, ButtonRow, DraftBoundary, Field, MoneyInput, Notice, PromptDialog, RecordPage, TableScroll } from "@/components/ui";
import { DeleteRecordButton } from "../DeleteRecordButton";

type Props = {
  projectId: string; contract: ContractDetail; roles: Set<string>;
  variations: Variation[] | null; payments: ConstructionPayment[] | null;
  onChanged: () => Promise<void>; unavailable: boolean;
};

/** Payments already made and changes agreed with the contractor are separate records. */
export function ContractTransactions({ projectId, contract, roles, variations, payments, onChanged, unavailable }: Props) {
  const [editor, setEditor] = useState<"payment" | "addition" | "reduction" | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reasonAction, setReasonAction] = useState<{ title: string; run: (reason: string) => Promise<unknown> } | null>(null);
  const prepare = hasAnyRole(roles, new Set(["finance", "project_manager"]));
  const finance = hasAnyRole(roles, new Set(["finance"]));
  const check = hasAnyRole(roles, new Set(["finance", "approver_cfo"]));
  const standing = ["active", "completed", "terminated"].includes(contract.status);
  async function act(run: () => Promise<unknown>) {
    if (busy || unavailable) return;
    setBusy(true); setError(null);
    try { await run(); setReasonAction(null); await onChanged(); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Could not save the change."); }
    finally { setBusy(false); }
  }
  if (editor) return <ContractTransactionEditor kind={editor} projectId={projectId} contract={contract} unavailable={unavailable} onClose={() => setEditor(null)} onChanged={onChanged} />;
  return <div className="stack">
    {error ? <Notice tone="error">{error}</Notice> : null}
    <ButtonRow>
      {standing && finance ? <Button variant="primary" disabled={busy || unavailable} onClick={() => setEditor("payment")}>Record payment already made</Button> : null}
      {standing && prepare ? <><Button disabled={busy || unavailable} onClick={() => setEditor("addition")}>Add variation</Button><Button disabled={busy || unavailable} onClick={() => setEditor("reduction")}>Add cost reduction</Button></> : null}
    </ButtonRow>
    <p>Payments update paid to date immediately. Changes adjust the contract value after approval. Invoices and certificates remain available as supporting records.</p>
    <TableScroll label="Contract variations and reductions"><thead><tr><th scope="col">Reference</th><th scope="col">Description</th><th scope="col">Change excluding tax</th><th scope="col">Status</th><th scope="col">Actions</th></tr></thead><tbody>
      {variations?.map(row => <tr key={row.id}><th scope="row">{row.variation_number}</th><td>{row.description}</td><td>{money(row.total_value_ex_tax, contract.currency_code)}</td><td>{row.status}</td><td>
        {prepare && row.status === "draft" ? <><Button disabled={busy || unavailable} onClick={() => void act(() => construction.submitVariation(projectId, row.id))}>Submit change</Button><DeleteRecordButton label="draft change" recordName={row.variation_number} description="Delete this draft change and its lines. The audit trail remains." onDelete={reason => construction.deleteDraftVariation(projectId, row.id, reason)} onDeleted={onChanged} /></> : null}
        {check && row.status === "submitted" ? <Button disabled={busy || unavailable} onClick={() => void act(() => construction.approveVariation(projectId, row.id))}>Approve change</Button> : null}
        {prepare && row.status === "submitted" ? <Button disabled={busy || unavailable} onClick={() => { setError(null); setReasonAction({ title: `Withdraw ${row.variation_number}`, run: reason => construction.withdrawVariation(projectId, row.id, reason) }); }}>Withdraw</Button> : null}
        {row.status === "approved" ? "Retained. Add an opposite variation to correct it." : null}
      </td></tr>)}
    </tbody></TableScroll>
    {variations === null ? <Notice tone="warning">Changes are unavailable. Refresh the contract to retry.</Notice> : variations.length === 0 ? <p>No variations or reductions recorded.</p> : null}
    <TableScroll label="Contract payment history"><thead><tr><th scope="col">Reference</th><th scope="col">Payment date</th><th scope="col">Amount including tax</th><th scope="col">Basis</th><th scope="col">Status</th><th scope="col">Actions</th></tr></thead><tbody>
      {payments?.map(row => <tr key={row.id}><th scope="row">{row.payment_reference}</th><td>{businessDate(row.payment_date)}</td><td>{money(row.amount, row.currency_code)}</td><td>{row.direct_contract_payment ? "Paid against contract" : "Invoice payment"}</td><td>{row.status}</td><td>
        {check && row.status === "confirmed" ? <Button disabled={busy || unavailable} onClick={() => { setError(null); setReasonAction({ title: `Reverse payment ${row.payment_reference}`, run: reason => construction.reversePayment(projectId, row.id, reason) }); }}>Reverse payment</Button> : null}
      </td></tr>)}
    </tbody></TableScroll>
    {payments === null ? <Notice tone="warning">Payments are unavailable. Refresh the contract to retry.</Notice> : payments.length === 0 ? <p>No payments recorded.</p> : null}
    {reasonAction ? <PromptDialog title={reasonAction.title} label="Reason" description="The original record and audit history remain. Totals will update after saving." busy={busy} error={error} onCancel={() => { if (!busy) setReasonAction(null); }} onSubmit={reason => void act(() => reasonAction.run(reason))} /> : null}
  </div>;
}

function ContractTransactionEditor({ kind, projectId, contract, unavailable, onClose, onChanged }: { kind: "payment" | "addition" | "reduction"; projectId: string; contract: ContractDetail; unavailable: boolean; onClose: () => void; onChanged: () => Promise<void> }) {
  const [reference, setReference] = useState("");
  const [date, setDate] = useState("");
  const [amount, setAmount] = useState("");
  const [description, setDescription] = useState("");
  const [evidence, setEvidence] = useState("");
  const [code, setCode] = useState(contract.lines[0]?.cost_code_id ?? "");
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const payment = kind === "payment";
  const title = payment ? "Record payment already made" : kind === "reduction" ? "Add cost reduction" : "Add variation";
  async function save() {
    if (busy || unavailable || saved) return;
    setBusy(true); setError(null);
    try {
      if (payment) await construction.recordPayment(projectId, contract.id, { payment_reference: reference, payment_date: date, amount, currency_id: contract.currency_id, proof_reference: evidence, notes: description, direct_contract_payment: true });
      else await construction.createVariation(projectId, contract.id, { variation_number: reference, description, requested_date: date, instruction_reference: evidence, cost_code_id: code, adjustment_amount: amount, adjustment_kind: kind, cause: kind === "reduction" ? "Client-supplied items / scope reduction" : "Additional scope" });
      setSaved(true); onClose(); await onChanged();
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Could not save this record."); }
    finally { setBusy(false); }
  }
  return <RecordPage title={title} subtitle={`${contract.contract_number} · ${contract.vendor_name}`} onClose={onClose}>
    <DraftBoundary dirty={!saved && !!(reference || date || amount || description || evidence)} busy={busy}>
      <form className="stack" onSubmit={event => { event.preventDefault(); void save(); }}>
        {error ? <Notice tone="error">{error}</Notice> : null}
        <p>{payment ? "Record an actual bank payment. This immediately counts as paid; no invoice or certificate is required. This does not instruct a bank transfer." : "Enter a positive amount. A reduction subtracts this amount from the contract after approval; the original signed value stays unchanged."}</p>
        <Field label="Reference"><input className="input" required maxLength={64} value={reference} onChange={e => setReference(e.target.value)} /></Field>
        <Field label={payment ? "Payment date" : "Change date"}><input className="input" type="date" required value={date} onChange={e => setDate(e.target.value)} /></Field>
        <Field label={payment ? "Amount paid including tax" : "Change amount excluding tax"}><MoneyInput required code={contract.currency_code} value={amount} onChange={setAmount} /></Field>
        {!payment ? <Field label="Contract scope"><select className="input" required value={code} onChange={e => setCode(e.target.value)}>{contract.cost_code_position.map(row => <option key={row.cost_code_id} value={row.cost_code_id}>{row.cost_code_name}</option>)}</select></Field> : null}
        <Field label={payment ? "Payment proof reference" : "Agreement / instruction reference"}><input className="input" required maxLength={payment ? 500 : 200} value={evidence} onChange={e => setEvidence(e.target.value)} /></Field>
        <Field label={payment ? "Notes" : "Description of added or removed items"} optional={payment}><textarea className="input" required={!payment} maxLength={1000} value={description} onChange={e => setDescription(e.target.value)} /></Field>
        <Button type="submit" variant="primary" disabled={busy || unavailable || saved}>{busy ? "Saving…" : payment ? "Save payment" : "Save draft change"}</Button>
      </form>
    </DraftBoundary>
  </RecordPage>;
}
