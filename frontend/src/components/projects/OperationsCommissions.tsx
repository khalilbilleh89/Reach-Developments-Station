"use client";

import { useState } from "react";
import { ApiError } from "@/lib/api";
import { operationsCommissions, type OperationsCommission, type OperationsInput, type OperationsRegister } from "@/lib/api/operationsCommissions";
import { useAnswer } from "@/lib/answer";
import { money } from "@/lib/format";
import { COMMISSION_READERS, COMMISSION_PREPARERS, hasAnyRole, type Roles } from "@/lib/roles";
import { Button, ButtonRow, Card, DraftBoundary, EmptyState, Field, FormActions, Loading, MoneyInput, Notice, PageHeader, RecordPage, TableScroll } from "@/components/ui";
import { DeleteRecordButton } from "./DeleteRecordButton";

export function OperationsCommissions({ projectId, roles, currencyCodes }: { projectId: string; roles: Roles; currencyCodes: Record<string, string> }) {
  const canWrite = hasAnyRole(roles, COMMISSION_PREPARERS);
  const answer = useAnswer(hasAnyRole(roles, COMMISSION_READERS), () => operationsCommissions.list(projectId), [projectId]);
  const [selected, setSelected] = useState<OperationsCommission | null>(null);
  const [editor, setEditor] = useState<{ row?: OperationsCommission } | null>(null);
  const [search, setSearch] = useState("");
  const refresh = () => { setSelected(null); setEditor(null); answer.retry(); };
  if (editor && answer.status === "ready") return <OperationsEditor row={editor.row} register={answer.data} currencyCodes={currencyCodes} onClose={refresh} onSave={async values => {
    if (editor.row) await operationsCommissions.update(projectId, editor.row, values);
    else await operationsCommissions.create(projectId, values);
    refresh();
  }} />;
  if (selected) return <RecordPage title={selected.beneficiary_name} eyebrow="Operations Commission" subtitle={selected.client_display} onClose={refresh} actions={canWrite ? <ButtonRow>
    <Button onClick={() => setEditor({ row: selected })}>Edit commission</Button>
    <DeleteRecordButton label="operations commission" confirmLabel="Delete commission" recordName={selected.beneficiary_name} description="Remove this entry from Operations Commission. The entry and its audit history are retained. This does not reverse a payment." onDelete={reason => operationsCommissions.remove(projectId, selected, reason)} onDeleted={async () => refresh()} />
  </ButtonRow> : undefined}>
    <dl className="stack"><div><dt>Client</dt><dd>{selected.client_display}</dd></div><div><dt>Beneficiary / to whom</dt><dd>{selected.beneficiary_name}</dd></div><div><dt>Fixed amount</dt><dd>{money(selected.amount, currencyCodes[selected.currency_id])}</dd></div><div><dt>Reason of commission</dt><dd style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{selected.reason}</dd></div></dl>
    <p className="footnote">Recorded commission only. Payment is not recorded here.</p>
  </RecordPage>;
  const needle = search.trim().toLowerCase();
  const shown = answer.status === "ready" ? answer.data.items.filter(row => [row.client_display, row.beneficiary_name, row.reason].some(value => value.toLowerCase().includes(needle))) : [];
  return <div className="stack">
    <PageHeader title="Operations Commission" icon="money" subtitle="Fixed commissions linked to a client, with a named recipient and reason." actions={canWrite && answer.status === "ready" ? <Button variant="primary" onClick={() => setEditor({})}>Add operations commission</Button> : undefined} />
    <Card title="Operations register" description="Each entry records one beneficiary and their fixed amount. Add another entry for an additional beneficiary.">
      {answer.status === "off" ? null : answer.status === "loading" ? <Loading label="Loading operations commissions" /> : answer.status === "denied" ? <Notice tone="info">Operations commissions are not available to your access level.</Notice> : answer.status === "failed" ? <Notice tone="error">{answer.message} <Button onClick={answer.retry}>Retry</Button></Notice> : <>
        <Field label="Search operations commissions"><input type="search" className="input" placeholder="Client, beneficiary or reason" value={search} onChange={event => setSearch(event.target.value)} /></Field>
        {shown.length ? <TableScroll label="Operations commissions"><thead><tr><th scope="col">Beneficiary / to whom</th><th scope="col">Client</th><th scope="col" className="num">Fixed amount</th><th scope="col">Reason</th></tr></thead><tbody>{shown.map(row => <tr key={row.id}><th scope="row"><Button variant="link" onClick={() => setSelected(row)}>{row.beneficiary_name}</Button></th><td>{row.client_display}</td><td className="num">{money(row.amount, currencyCodes[row.currency_id])}</td><td style={{ overflowWrap: "anywhere" }}>{row.reason}</td></tr>)}</tbody></TableScroll> : <EmptyState title={search ? "No matching operations commissions" : "No operations commissions yet"} hint={search ? "Try a different client, beneficiary or reason." : "Add a client-linked fixed commission to get started."} />}
      </>}
      <p className="footnote">These entries record commission amounts, not payments. Sales commission calculations remain separate.</p>
    </Card>
  </div>;
}

export function OperationsEditor({ row, register, currencyCodes, onClose, onSave }: { row?: OperationsCommission; register: OperationsRegister; currencyCodes: Record<string, string>; onClose: () => void; onSave: (values: OperationsInput) => Promise<void> }) {
  const initial: OperationsInput = { client_id: row?.client_id ?? "", beneficiary_name: row?.beneficiary_name ?? "", amount: row?.amount ?? "", reason: row?.reason ?? "" };
  const [values, setValues] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const set = (key: keyof OperationsInput, value: string) => setValues({ ...values, [key]: value });
  return <RecordPage title={row ? "Edit operations commission" : "Add operations commission"} onClose={onClose}>
    <DraftBoundary busy={busy} dirty={JSON.stringify(values) !== JSON.stringify(initial)}>
      <form className="stack" onSubmit={async event => {
        event.preventDefault(); if (busy) return;
        setBusy(true); setError(null);
        try { await onSave(values); } catch (caught) { setError(caught instanceof ApiError ? caught.message : "Could not save. Your entries have been kept."); } finally { setBusy(false); }
      }}>
        {error ? <Notice tone="error">{error}</Notice> : null}
        <fieldset disabled={busy} className="marketing-fieldset stack">
          <Field label="Client"><select required className="input" value={values.client_id} onChange={event => set("client_id", event.target.value)}><option value="">Choose a client</option>{row && !register.clients.some(client => client.id === row.client_id) ? <option value={row.client_id}>{row.client_display} (existing entry)</option> : null}{register.clients.map(client => <option key={client.id} value={client.id}>{client.display_name} · {client.client_number}</option>)}</select></Field>
          {!register.clients.length && !row ? <Notice tone="info">Add an active client in Buyers before recording an operations commission.</Notice> : null}
          <Field label="Beneficiary / to whom"><input required className="input" maxLength={200} value={values.beneficiary_name} onChange={event => set("beneficiary_name", event.target.value)} /></Field>
          <Field label="Fixed amount" hint="Enter a positive amount with up to two decimal places."><MoneyInput required code={currencyCodes[row?.currency_id ?? register.currency_id] ?? null} value={values.amount} onChange={value => set("amount", value)} /></Field>
          <Field label="Reason of commission"><textarea required className="input" rows={4} maxLength={2000} value={values.reason} onChange={event => set("reason", event.target.value)} /></Field>
        </fieldset>
        <FormActions><Button type="submit" variant="primary" disabled={busy || !values.client_id}>{busy ? "Saving…" : "Save commission"}</Button><Button disabled={busy} data-leaves-editor onClick={onClose}>Cancel</Button></FormActions>
      </form>
    </DraftBoundary>
  </RecordPage>;
}
