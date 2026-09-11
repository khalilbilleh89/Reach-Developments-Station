"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, prelaunch } from "@/lib/api";
import type { PreLaunchRegister } from "@/lib/api";
import { businessDate, money } from "@/lib/format";
import { CASHFLOW_CONFIRMERS, PRELAUNCH_RECORDERS, hasAnyRole } from "@/lib/roles";
import type { Roles } from "@/lib/roles";
import { sectionDescription } from "@/components/shell/navigation";
import {
  Badge,
  Button,
  ButtonRow,
  Card,
  EmptyState,
  Field,
  FieldRow,
  FormDialog,
  Loading,
  Position,
  PositionFigure,
  FormSection,
  MoneyInput,
  Notice,
  PageHeader,
  PromptDialog,
  TableScroll,
} from "@/components/ui";
import type { Tone } from "@/components/ui";

const CATEGORIES = [
  ["land_fees", "Authority / land fees"],
  ["permits", "Permit and authority fees"],
  ["utilities", "Utilities"],
  ["design", "Design"],
  ["consultants", "Consultants"],
  ["insurance", "Insurance"],
  ["developer_overhead", "Developer overhead"],
  ["marketing", "Marketing"],
  ["tax", "Tax"],
  ["other", "Other pre-launch expense"],
] as const;

const categoryLabel = (key: string) => CATEGORIES.find(([value]) => value === key)?.[1] ?? key;
const statusTone = (status: string): Tone =>
  status === "confirmed" ? "success" : status === "reversed" ? "muted" : "warning";

export function PreLaunchTab({
  projectId,
  currencyId,
  currencyCode,
  roles,
}: {
  projectId: string;
  currencyId: string;
  currencyCode: string | null;
  roles: Roles;
}) {
  const [register, setRegister] = useState<PreLaunchRegister | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [adding, setAdding] = useState(false);
  const [reversing, setReversing] = useState<string | null>(null);
  const canRecord = hasAnyRole(roles, PRELAUNCH_RECORDERS);
  const canConfirm = hasAnyRole(roles, CASHFLOW_CONFIRMERS);

  const [readError, setReadError] = useState<string | null>(null);
  const [retrying, setRetrying] = useState(false);
  const load = useCallback(async () => {
    setRetrying(true);
    try {
      setRegister(await prelaunch.register(projectId));
      setReadError(null);
    } catch (caught) {
      setReadError(caught instanceof ApiError ? caught.message : "Could not load Pre-Launch expenses.");
    } finally {
      setRetrying(false);
    }
  }, [projectId]);

  useEffect(() => {
    void (async () => {
      await load();
    })();
  }, [load]);

  const run = async (action: () => Promise<unknown>) => {
    setBusy(true);
    setError(null);
    try {
      await action();
      setAdding(false);
      setReversing(null);
      await load();
    } catch (caught) {
      // Refresh eligibility after a stale-state or permission refusal, without
      // retrying the write or losing the server's explanation.
      if (caught instanceof ApiError && (caught.status === 403 || caught.status === 409)) await load();
      setError(caught instanceof ApiError ? caught.message : "That action could not be completed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="stack">
      <PageHeader
        icon="money"
        title="Pre-Launch"
        subtitle={sectionDescription("prelaunch")}
        actions={canRecord ? <Button variant="primary" onClick={() => setAdding(true)}>Add expense</Button> : undefined}
      />
      {error ? <Notice tone="error">{error}</Notice> : null}
      {readError ? <><Notice tone="error">{readError}</Notice><Button disabled={retrying} onClick={() => void load()}>{retrying ? "Retrying…" : "Retry Pre-Launch expenses"}</Button></> : null}
      {register ? (
        <Card tone="command" title="Expense position"><Position compact>
          <PositionFigure label="Recorded amount" value={money(register.recorded_amount, currencyCode)} note="Not confirmed cash" />
          <PositionFigure lead label="Confirmed paid amount" value={money(register.confirmed_paid_amount, currencyCode)} note="Included once in project cashflow" />
        </Position><p className="footnote">Recorded means entered but not yet confirmed as cash. A different authorised Finance or CFO user confirms payment.</p></Card>
      ) : null}
      <Card flush>
        {register === null ? readError ? null : <Loading label="Loading Pre-Launch expenses" shape="rows" /> : register.expenses.length === 0 ? (
          <div className="card-body"><EmptyState title="No Pre-Launch expenses" hint="Record authority, utility and other allowed development expenses here." /></div>
        ) : (
          <TableScroll label="Pre-Launch expense register" fixedFirst>
            <thead><tr><th scope="col">Description</th><th scope="col">Category</th><th scope="col">Counterparty / authority</th><th scope="col">Date</th><th scope="col" className="num">Amount</th><th scope="col">Status</th><th scope="col">Reference</th><th scope="col"><span className="visually-hidden">Actions</span></th></tr></thead>
            <tbody>{register.expenses.map((row) => (
              <tr key={row.id}>
                <th scope="row" className="cell-prose">{row.notes ?? row.movement_reference}</th>
                <td>{categoryLabel(row.category)}</td>
                <td>{row.counterparty_reference ?? "—"}</td>
                <td>{businessDate(row.movement_date)}</td>
                <td className="num">{money(row.amount, row.currency_code ?? currencyCode)}</td>
                <td><Badge tone={statusTone(row.status)}>{row.status === "confirmed" ? "Confirmed" : row.status === "reversed" ? "Reversed" : "Recorded"}</Badge></td>
                <td>{row.invoice_reference ?? row.evidence_reference ?? "—"}</td>
                <td className="cell-prose"><ButtonRow>
                  {canConfirm && row.status === "recorded" ? (
                    <div>
                      <Button small disabled={busy || !row.can_confirm} onClick={() => void run(() => prelaunch.confirm(projectId, row.id))}>Confirm</Button>
                      {!row.can_confirm ? <p className="footnote">{row.confirmation_blocker ?? "Confirmation is unavailable. Refresh this register to check current eligibility."}</p> : null}
                    </div>
                  ) : null}
                  {canConfirm && row.status === "confirmed" ? <Button small variant="danger" disabled={busy} onClick={() => setReversing(row.id)}>Reverse</Button> : null}
                </ButtonRow></td>
              </tr>
            ))}</tbody>
          </TableScroll>
        )}
      </Card>
      {adding ? <ExpenseDialog currencyId={currencyId} currencyCode={currencyCode} busy={busy} error={error} onCancel={() => { if (!busy) setAdding(false); }} onSubmit={(body) => { void run(() => prelaunch.record(projectId, body)); }} /> : null}
      {reversing ? <PromptDialog title="Reverse this expense" label="Reason" hint="The original remains in history and is removed from current actual cash." confirmLabel="Reverse" busy={busy} error={error} onCancel={() => { if (!busy) setReversing(null); }} onSubmit={(reason) => { void run(() => prelaunch.reverse(projectId, reversing, reason)); }} /> : null}
    </div>
  );
}

function ExpenseDialog({ currencyId, currencyCode, busy, error, onCancel, onSubmit }: { currencyId: string; currencyCode: string | null; busy: boolean; error: string | null; onCancel: () => void; onSubmit: (body: Record<string, unknown>) => void }) {
  const [category, setCategory] = useState("permits");
  const [description, setDescription] = useState("");
  const [amount, setAmount] = useState("");
  const [date, setDate] = useState("");
  const [counterparty, setCounterparty] = useState("");
  const [reference, setReference] = useState("");
  const [evidence, setEvidence] = useState("");
  return <FormDialog title="Add Pre-Launch expense" description="This records an entry. It is not cash until another authorised user confirms it." confirmLabel="Record expense" busy={busy} disabled={!description || !amount || !date} onCancel={onCancel} onSubmit={() => onSubmit({ category, amount, movement_date: date, currency_id: currencyId, counterparty_reference: counterparty || null, invoice_reference: reference || null, evidence_reference: evidence || null, notes: description })}>
    {error ? <Notice tone="error">{error}</Notice> : null}
    <FormSection title="Expense"><Field label="Description / notes"><input className="input" required maxLength={2000} value={description} onChange={(event) => setDescription(event.target.value)} /></Field>
    <FieldRow><Field label="Category"><select className="input" value={category} onChange={(event) => setCategory(event.target.value)}>{CATEGORIES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></Field><Field label="Amount"><MoneyInput code={currencyCode} value={amount} onChange={setAmount} /></Field></FieldRow>
    </FormSection><FormSection title="Payment and evidence"><FieldRow><Field label="Payment / movement date"><input className="input" type="date" required value={date} onChange={(event) => setDate(event.target.value)} /></Field><Field label="Counterparty / authority" optional><input className="input" value={counterparty} onChange={(event) => setCounterparty(event.target.value)} /></Field></FieldRow>
    <FieldRow><Field label="Reference" optional><input className="input" value={reference} onChange={(event) => setReference(event.target.value)} /></Field><Field label="Evidence / proof" optional><input className="input" value={evidence} onChange={(event) => setEvidence(event.target.value)} /></Field></FieldRow>
    </FormSection>
  </FormDialog>;
}
