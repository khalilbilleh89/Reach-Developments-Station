"use client";

import { useRef, useState } from "react";
import { ApiError, consultantEngineering as api, prelaunch } from "@/lib/api";
import type { ConsultantEngagement, ConsultantStage, DesignStagePayment, DesignPaymentProof, PreLaunchExpense } from "@/lib/api/types";
import { useAnswer } from "@/lib/answer";
import { businessDate, money, todayISO } from "@/lib/format";
import { CASHFLOW_READERS, CASHFLOW_CONFIRMERS, PRELAUNCH_RECORDERS, hasAnyRole } from "@/lib/roles";
import type { Roles } from "@/lib/roles";
import { Badge, Button, ButtonRow, DraftBoundary, EmptyState, Field, FieldRow, FormActions, FormSection, KeyValue, KeyValueGrid, Loading, MoneyInput, Notice, PromptDialog, RecordPage, SubPanel } from "@/components/ui";

export const paymentExpected = (row: PreLaunchExpense) => ({
  category: row.category, amount: row.amount, amount_ex_vat: row.amount_ex_vat, vat_rate_percent: row.vat_rate_percent,
  movement_date: row.movement_date, counterparty_reference: row.counterparty_reference,
  invoice_reference: row.invoice_reference, evidence_reference: row.evidence_reference, notes: row.notes,
});

type Prompt = { kind: "remove" | "reverse"; payment: DesignStagePayment } | { kind: "proof"; payment: DesignStagePayment; proof: DesignPaymentProof };

export function DesignPayments({ projectId, roles, stages, agreement }: { projectId: string; roles: Roles; stages: ConsultantStage[]; agreement: ConsultantEngagement }) {
  const allowed = hasAnyRole(roles, CASHFLOW_READERS);
  const canRecord = hasAnyRole(roles, PRELAUNCH_RECORDERS);
  const canConfirm = hasAnyRole(roles, CASHFLOW_CONFIRMERS);
  const answer = useAnswer(allowed, () => api.payments(projectId), [projectId]);
  const [editor, setEditor] = useState<{ stage: ConsultantStage; initial?: DesignStagePayment } | null>(null);
  const [prompt, setPrompt] = useState<Prompt | null>(null);
  const [busy, setBusy] = useState(false);
  const submitting = useRef(false);
  const [error, setError] = useState<string | null>(null);
  const act = async (action: () => Promise<unknown>) => {
    if (submitting.current) return;
    submitting.current = true; setBusy(true); setError(null);
    try { await action(); setPrompt(null); answer.retry(); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Payment action failed."); }
    finally { submitting.current = false; setBusy(false); }
  };
  if (answer.status === "off") return null;
  if (answer.status === "denied") return <Notice tone="info">Payment details are not available to your role.</Notice>;
  if (answer.status === "failed") return <Notice tone="error">{answer.message} <Button onClick={answer.retry}>Retry stage payments</Button></Notice>;
  if (answer.status === "loading") return <Loading label="Loading stage payments" />;
  const data = answer.data;
  return <SubPanel title="Stage payments">
    <p className="footnote">Project currency · agreed stage fees include VAT. Recorded payments are unconfirmed; confirmed paid amounts enter cashflow once. A negative balance means confirmed payments exceed the agreed fee.</p>
    {error ? <Notice tone="error">{error}</Notice> : null}
    {stages.length === 0 ? <EmptyState compact title="No stages to pay" hint="Add a design stage and record its agreed fee in the programme." /> : stages.map(stage => {
      const position = data.stages.find(item => item.stage_id === stage.id);
      const rows = data.payments.filter(item => item.stage_id === stage.id);
      return <section className="stack" key={stage.id}>
        <h3>{stage.name}</h3>
        {position ? <KeyValueGrid columns={4}>
          <KeyValue label="Agreed stage payment" value={position.agreed_payment_amount == null ? "Not agreed" : money(position.agreed_payment_amount, data.currency_code)} />
          <KeyValue label="Recorded / unconfirmed" value={money(position.recorded_amount, data.currency_code)} />
          <KeyValue label="Confirmed paid" value={money(position.confirmed_paid_amount, data.currency_code)} />
          <KeyValue label="Balance after confirmed payments" value={position.remaining_amount == null ? "Agreed fee not entered" : money(position.remaining_amount, data.currency_code)} />
        </KeyValueGrid> : <Notice tone="info">Payment position unavailable. <Button onClick={answer.retry}>Refresh payments</Button></Notice>}
        {canRecord && stage.status === "completed" && agreement.status !== "draft" ? <Button disabled={busy} onClick={() => { setError(null); setEditor({ stage }); }}>Record payment for {stage.name}</Button> : <p className="footnote">{stage.status !== "completed" ? "Complete this stage and record its completion date before adding payments." : agreement.status === "draft" ? "Activate the agreement before recording payment." : "Payment recording is available to Project Manager and Finance."}</p>}
        {rows.length === 0 ? <p className="footnote">No payments recorded for this stage.</p> : rows.map(row => <article className="stack" key={row.id}>
          <div><strong>{money(row.expense.amount, row.expense.currency_code ?? data.currency_code)}</strong> · <Badge>{row.expense.removed_without_confirmation ? "Removed" : row.expense.status}</Badge> · {businessDate(row.expense.movement_date)} · {row.expense.movement_reference}</div>
          <p className="footnote">Excluding VAT {money(row.expense.amount_ex_vat, row.expense.currency_code ?? data.currency_code)} · VAT {money(row.expense.vat_amount, row.expense.currency_code ?? data.currency_code)} · {row.expense.invoice_reference ?? "No payment reference"}</p>
          {row.expense.reversal_reason ? <p className="footnote">{row.expense.reversal_reason}</p> : null}
          <ButtonRow>
            {row.expense.can_edit ? <Button small disabled={busy} onClick={() => setEditor({ stage, initial: row })}>Edit payment</Button> : null}
            {row.expense.can_remove ? <Button small variant="danger" disabled={busy} onClick={() => setPrompt({ kind: "remove", payment: row })}>Delete recorded payment</Button> : null}
            {canConfirm && row.expense.status === "recorded" ? <Button small disabled={busy || !row.expense.can_confirm} onClick={() => void act(() => api.confirmPayment(projectId, row.id, paymentExpected(row.expense)))}>Confirm payment</Button> : null}
            {canConfirm && row.expense.status === "confirmed" ? <Button small variant="danger" disabled={busy} onClick={() => setPrompt({ kind: "reverse", payment: row })}>Reverse payment</Button> : null}
          </ButtonRow>
          {row.expense.status === "recorded" && !row.expense.can_confirm ? <p className="footnote">{row.expense.confirmation_blocker}</p> : null}
          <h4>PDF proof of payment (optional)</h4>
          {row.proofs.length ? <ul>{row.proofs.map(proof => <li key={proof.id}><Button small variant="link" onClick={() => void act(() => api.downloadPaymentProof(projectId, row.id, proof))}>{proof.filename}</Button>{canRecord ? <Button small variant="danger" disabled={busy} onClick={() => setPrompt({ kind: "proof", payment: row, proof })}>Delete PDF proof</Button> : null}</li>)}</ul> : <p className="footnote">No PDF attached. Proof can be added at any time.</p>}
          {canRecord ? <ProofUpload projectId={projectId} paymentId={row.id} onChanged={answer.retry} /> : null}
        </article>)}
      </section>;
    })}
    {editor ? <PaymentForm key={editor.initial?.id ?? editor.stage.id} projectId={projectId} stage={editor.stage} agreement={agreement} currencyId={data.currency_id} currencyCode={data.currency_code} initial={editor.initial} onCancel={() => setEditor(null)} onDone={() => { setEditor(null); answer.retry(); }} /> : null}
    {prompt ? <PromptDialog title={prompt.kind === "proof" ? `Delete ${prompt.proof.filename}` : `${prompt.kind === "remove" ? "Delete recorded" : "Reverse"} payment ${prompt.payment.expense.movement_reference}`} label="Reason" hint="The payment, tax details, PDF bytes and audit remain in history. Removed or reversed payments leave current stage totals." confirmLabel={prompt.kind === "reverse" ? "Reverse payment" : "Delete"} busy={busy} error={error} onCancel={() => { if (!busy) setPrompt(null); }} onSubmit={reason => void act(() => prompt.kind === "proof" ? api.deletePaymentProof(projectId, prompt.payment.id, prompt.proof.id, reason) : prompt.kind === "remove" ? api.removePayment(projectId, prompt.payment.id, paymentExpected(prompt.payment.expense), reason) : api.reversePayment(projectId, prompt.payment.id, reason))} /> : null}
  </SubPanel>;
}

function ProofUpload({ projectId, paymentId, onChanged }: { projectId: string; paymentId: string; onChanged: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const submitting = useRef(false);
  return <DraftBoundary dirty={!!file} busy={busy}><form onSubmit={event => { event.preventDefault(); if (!file || submitting.current) return; submitting.current = true; setBusy(true); setError(null); void api.uploadPaymentProof(projectId, paymentId, file).then(() => { setFile(null); onChanged(); }).catch(caught => setError(caught instanceof Error ? caught.message : "PDF upload failed; your selected file is kept.")).finally(() => { submitting.current = false; setBusy(false); }); }}>
    <Field label="Attach optional PDF proof" hint="PDF, up to 10 MB. Payment entry does not require a file."><input className="input" type="file" accept=".pdf,application/pdf" disabled={busy} onChange={event => setFile(event.target.files?.[0] ?? null)} /></Field>
    {error ? <Notice tone="error">{error}</Notice> : null}
    <Button type="submit" disabled={!file || busy}>{busy ? "Uploading…" : "Upload PDF proof"}</Button>
  </form></DraftBoundary>;
}

function PaymentForm({ projectId, stage, agreement, currencyId, currencyCode, initial, onCancel, onDone }: { projectId: string; stage: ConsultantStage; agreement: ConsultantEngagement; currencyId: string; currencyCode: string | null; initial?: DesignStagePayment; onCancel: () => void; onDone: () => void }) {
  const [net, setNet] = useState(initial?.expense.amount_ex_vat ?? "");
  const [rate, setRate] = useState(initial?.expense.vat_rate_percent ?? "");
  const [date, setDate] = useState(initial?.expense.movement_date ?? todayISO());
  const [reference, setReference] = useState(initial?.expense.invoice_reference ?? "");
  const [notes, setNotes] = useState(initial?.expense.notes ?? `${agreement.consultant_name} · ${stage.name}`);
  const [file, setFile] = useState<File | null>(null);
  const [requestId] = useState(() => crypto.randomUUID());
  const [saved, setSaved] = useState<DesignStagePayment | null>(null);
  const [busy, setBusy] = useState(false);
  const submitting = useRef(false);
  const [error, setError] = useState<string | null>(null);
  const preview = useAnswer(!!net, () => prelaunch.preview(projectId, { amount_ex_vat: net, vat_rate_percent: rate || "0" }), [projectId, net, rate]);
  const dirty = !saved && (net !== (initial?.expense.amount_ex_vat ?? "") || rate !== (initial?.expense.vat_rate_percent ?? "") || date !== (initial?.expense.movement_date ?? todayISO()) || reference !== (initial?.expense.invoice_reference ?? "") || notes !== (initial?.expense.notes ?? `${agreement.consultant_name} · ${stage.name}`)) || !!file;
  const submit = async () => {
    if (submitting.current || (!saved && preview.status !== "ready")) return;
    submitting.current = true; setBusy(true); setError(null);
    let payment = saved;
    try {
      const changes = { category: "consultants", amount_ex_vat: net, vat_rate_percent: rate || "0", movement_date: date, counterparty_reference: agreement.consultant_name, invoice_reference: reference || null, evidence_reference: initial?.expense.evidence_reference ?? null, notes };
      if (!payment) {
        payment = initial ? await api.editPayment(projectId, initial.id, { expected: paymentExpected(initial.expense), changes }) : await api.recordPayment(projectId, stage.id, { ...changes, request_id: requestId, expected_stage_updated_at: stage.updated_at, currency_id: currencyId });
        setSaved(payment);
      }
      if (file) { await api.uploadPaymentProof(projectId, payment.id, file); setFile(null); }
      onDone();
    } catch (caught) { setError(`${payment ? "Payment saved. PDF upload failed; retry to attach it. " : ""}${caught instanceof ApiError || caught instanceof Error ? caught.message : "Payment could not be saved."}`); }
    finally { submitting.current = false; setBusy(false); }
  };
  return <RecordPage title={initial ? "Edit stage payment" : `Record payment · ${stage.name}`} eyebrow={agreement.consultant_name} onClose={saved ? onDone : onCancel}><DraftBoundary dirty={dirty} busy={busy}><form onSubmit={event => { event.preventDefault(); void submit(); }}>
    <p className="footnote">Stage completed {businessDate(stage.actual_completion_date)}. Saving records an unconfirmed payment; Finance/CFO confirmation makes it paid. PDF proof is optional.</p>
    {error ? <Notice tone="error">{error}</Notice> : null}
    <FormSection title="Payment details"><FieldRow><Field label="Amount excluding VAT"><MoneyInput code={currencyCode} value={net} onChange={setNet} disabled={busy || !!saved} /></Field><Field label="VAT (%)" optional><input className="input" type="number" min="0" max="100" step="0.0001" value={rate} disabled={busy || !!saved} onChange={event => setRate(event.target.value)} /></Field></FieldRow>
      {preview.status === "ready" ? <KeyValueGrid columns={2}><KeyValue label="VAT amount" value={money(preview.data.vat_amount, currencyCode)} /><KeyValue label="Total including VAT" value={money(preview.data.amount, currencyCode)} /></KeyValueGrid> : preview.status === "failed" ? <Notice tone="error">{preview.message}<Button onClick={preview.retry}>Retry total</Button></Notice> : preview.status === "loading" ? <Loading label="Calculating payment total" /> : null}
      <FieldRow><Field label="Payment date"><input className="input" type="date" required min={stage.actual_completion_date ?? undefined} max={todayISO()} value={date} disabled={busy || !!saved} onChange={event => setDate(event.target.value)} /></Field><Field label="Payment / bank reference" optional><input className="input" value={reference} disabled={busy || !!saved} maxLength={200} onChange={event => setReference(event.target.value)} /></Field></FieldRow>
      <Field label="Notes" optional><textarea className="input" value={notes} maxLength={2000} disabled={busy || !!saved} onChange={event => setNotes(event.target.value)} /></Field>
      <Field label="PDF proof of payment" optional hint="Attach now or later. PDF up to 10 MB."><input className="input" type="file" accept=".pdf,application/pdf" disabled={busy} onChange={event => setFile(event.target.files?.[0] ?? null)} /></Field>
    </FormSection><FormActions><Button type="submit" variant="primary" disabled={busy || (!saved && (preview.status !== "ready" || !date))}>{busy ? "Saving…" : saved ? "Retry PDF / finish" : "Save payment"}</Button><Button data-leaves-editor disabled={busy} onClick={saved ? onDone : onCancel}>{saved ? "Finish without PDF" : "Cancel"}</Button></FormActions>
  </form></DraftBoundary></RecordPage>;
}
