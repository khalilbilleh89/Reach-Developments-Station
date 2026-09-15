"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, prelaunch } from "@/lib/api";
import type { PreLaunchExpense, PreLaunchRegister } from "@/lib/api";
import { businessDate, money } from "@/lib/format";
import { CASHFLOW_CONFIRMERS, PRELAUNCH_RECORDERS, hasAnyRole } from "@/lib/roles";
import type { Roles } from "@/lib/roles";
import { sectionDescription } from "@/components/shell/navigation";
import {
  Badge,
  Icon,
  Button,
  ButtonRow,
  Card,
  EmptyState,
  Field,
  FieldRow,
  RecordPage,
  DraftBoundary,
  FormActions,
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

const editableFields = (row: PreLaunchExpense) => ({
  category: row.category, amount: row.amount, movement_date: row.movement_date,
  counterparty_reference: row.counterparty_reference, invoice_reference: row.invoice_reference,
  evidence_reference: row.evidence_reference, notes: row.notes,
});

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
  const [editing, setEditing] = useState<PreLaunchExpense | null>(null);
  const [removing, setRemoving] = useState<PreLaunchExpense | null>(null);
  const submitting = useRef(false);
  const [reversing, setReversing] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [schedule, setSchedule] = useState(false);
  const [showEmptyCategories, setShowEmptyCategories] = useState(false);
  const expenses = register?.expenses.filter(row =>
    (!status || (status === "removed" ? row.removed_without_confirmation : !row.removed_without_confirmation && row.status === status)) &&
    [row.notes, row.movement_reference, row.counterparty_reference, row.invoice_reference, categoryLabel(row.category)].some(value => value?.toLowerCase().includes(search.toLowerCase().trim()))
  ) ?? [];
  const nonzero = (value: string) => /[1-9]/.test(value);
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
    if (submitting.current) return;
    submitting.current = true;
    setBusy(true);
    setError(null);
    try {
      await action();
      setAdding(false);
      setReversing(null);
      setEditing(null);
      setRemoving(null);
      await load();
    } catch (caught) {
      // Refresh eligibility after a stale-state or permission refusal, without
      // retrying the write or losing the server's explanation.
      if (caught instanceof ApiError && (caught.status === 403 || caught.status === 409)) await load();
      setError(caught instanceof ApiError ? caught.message : "That action could not be completed.");
    } finally {
      submitting.current = false;
      setBusy(false);
    }
  };

  const expenseActions = (row: PreLaunchExpense) => (<ButtonRow>
                  {row.can_edit ? <Button small disabled={busy} onClick={() => { setError(null); setEditing(row); }}>Edit</Button> : null}
                  {row.can_remove ? <Button small variant="danger" disabled={busy} onClick={() => { setError(null); setRemoving(row); }}>Remove</Button> : null}
                  {row.status === "recorded" && !row.can_edit && !row.can_remove ? <p className="footnote">{row.removal_blocker ?? row.edit_blocker}</p> : null}
                  {canConfirm && row.status === "recorded" ? (
                    <div>
                      <Button small disabled={busy || !row.can_confirm} onClick={() => void run(() => prelaunch.confirm(projectId, row.id, editableFields(row)))}>Confirm</Button>
                      {!row.can_confirm ? <p className="footnote">{row.confirmation_blocker ?? "Confirmation is unavailable. Refresh this register to check current eligibility."}</p> : null}
                    </div>
                  ) : null}
                  {canConfirm && row.status === "confirmed" ? <Button small variant="danger" disabled={busy} onClick={() => setReversing(row.id)}>Reverse</Button> : null}
                </ButtonRow>);
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
        </Position><p className="footnote">Recorded means entered but not yet confirmed as cash. A different authorised Finance or CFO user confirms payment. Master Administrator / Boss can confirm their own expenses.</p></Card>
      ) : null}
      <div className="prelaunch-ledger-layout">
      <Card title="Expense register" description="Search descriptions, counterparties, references or categories. Filters apply to the register; position totals remain project-wide." actions={<Button small aria-pressed={schedule} onClick={() => setSchedule(!schedule)}>{schedule ? "Show entries" : "Show schedule"}</Button>}>
        <FieldRow><Field label="Search expenses"><input className="input" type="search" value={search} onChange={event => setSearch(event.target.value)} /></Field><Field label="Expense status"><select className="input" value={status} onChange={event => setStatus(event.target.value)}><option value="">All statuses</option><option value="recorded">Recorded</option><option value="confirmed">Confirmed</option><option value="reversed">Reversed</option><option value="removed">Removed</option></select></Field></FieldRow>
        {register ? <p className="register-result-count">{expenses.length} matching {expenses.length === 1 ? "entry" : "entries"}{search || status ? <Button small variant="link" onClick={() => { setSearch(""); setStatus(""); }}>Clear filters</Button> : null}</p> : null}
        {register === null ? readError ? null : <Loading label="Loading Pre-Launch expenses" shape="rows" /> : register.expenses.length === 0 ? (
          <div className="card-body"><EmptyState title="No Pre-Launch expenses" hint="Record authority, utility and other allowed development expenses here." /></div>
        ) : expenses.length === 0 ? <EmptyState title="No matching expenses" actions={<Button onClick={() => { setSearch(""); setStatus(""); }}>Reset filters</Button>} /> : (
          schedule ? <TableScroll label="Pre-Launch expense register" fixedFirst>
            <thead><tr><th scope="col">Description</th><th scope="col">Category</th><th scope="col">Counterparty / authority</th><th scope="col">Date</th><th scope="col" className="num">Amount</th><th scope="col">Status</th><th scope="col">Reference</th><th scope="col"><span className="visually-hidden">Actions</span></th></tr></thead>
            <tbody>{expenses.map((row) => (
              <tr key={row.id}>
                <th scope="row" className="cell-prose">{row.notes ?? row.movement_reference}</th>
                <td>{categoryLabel(row.category)}</td>
                <td>{row.counterparty_reference ?? "—"}</td>
                <td>{businessDate(row.movement_date)}</td>
                <td className="num">{money(row.amount, row.currency_code ?? currencyCode)}</td>
                <td><Badge tone={statusTone(row.status)}>{row.removed_without_confirmation ? "Removed" : row.status === "confirmed" ? "Confirmed" : row.status === "reversed" ? "Reversed" : "Recorded"}</Badge>{row.reversal_reason ? <p className="footnote">{row.reversal_reason}</p> : null}</td>
                <td><span className="cell-secondary">Invoice: {row.invoice_reference ?? "—"}</span><span className="cell-secondary">Evidence: {row.evidence_reference ?? "—"}</span></td>
                <td className="cell-prose">{expenseActions(row)}</td>
              </tr>
            ))}</tbody>
          </TableScroll> : <div className="expense-entry-list">{expenses.map(row => <article className="expense-entry" key={row.id}>
            <header><div><span className="eyebrow"><Icon name="money" />{categoryLabel(row.category)}</span><h3>{row.notes ?? row.movement_reference}</h3><p className="footnote">{row.counterparty_reference ?? "Counterparty not recorded"}</p></div><div className="expense-entry-amount"><strong>{money(row.amount, row.currency_code ?? currencyCode)}</strong><Badge tone={statusTone(row.status)}>{row.removed_without_confirmation ? "Removed" : row.status === "confirmed" ? "Confirmed" : row.status === "reversed" ? "Reversed" : "Recorded"}</Badge></div></header>
            <dl><div><dt>Movement date</dt><dd>{businessDate(row.movement_date)}</dd></div><div><dt>Movement reference</dt><dd>{row.movement_reference}</dd></div><div><dt>Invoice reference</dt><dd>{row.invoice_reference ?? "Not recorded"}</dd></div><div><dt>Supporting evidence</dt><dd>{row.evidence_reference ?? "Not recorded"}</dd></div></dl>
            {row.reversal_reason ? <p className="footnote">{row.reversal_reason}</p> : null}<footer>{expenseActions(row)}</footer>
          </article>)}</div>
        )}
      </Card>
      {register ? <Card title="Expenses by category" description="Current recorded and confirmed expenses. Removed and reversed entries are excluded." actions={<Button small aria-pressed={showEmptyCategories} onClick={() => setShowEmptyCategories(!showEmptyCategories)}>{showEmptyCategories ? "Hide empty categories" : "Include empty categories"}</Button>}>
        <div className="expense-category-list">{register.categories.filter(category => showEmptyCategories || nonzero(category.recorded_amount) || nonzero(category.confirmed_paid_amount)).map(category => <section key={category.category}><h3>{categoryLabel(category.category)}</h3><dl><div><dt>Recorded</dt><dd>{money(category.recorded_amount, currencyCode)}</dd></div><div><dt>Confirmed paid</dt><dd>{money(category.confirmed_paid_amount, currencyCode)}</dd></div><div><dt>Total expenses</dt><dd>{money(category.total_amount, currencyCode)}</dd></div><div><dt>Share of confirmed paid</dt><dd>{nonzero(register.confirmed_paid_amount) ? category.confirmed_share_percent + "%" : "No confirmed payments"}</dd></div></dl></section>)}</div>
        <p className="footnote">Total expenses include unconfirmed entries; confirmed paid is the cash amount. Percentages use confirmed paid only.</p>
      </Card> : null}
      </div>
      {adding ? <ExpenseDialog currencyId={currencyId} currencyCode={currencyCode} busy={busy} error={error} onCancel={() => { if (!busy) setAdding(false); }} onSubmit={(body) => { void run(() => prelaunch.record(projectId, body)); }} /> : null}
      {editing ? <ExpenseDialog key={editing.id} initial={editing} currencyId={currencyId} currencyCode={editing.currency_code ?? currencyCode} busy={busy} error={error} onCancel={() => { if (!busy) setEditing(null); }} onSubmit={(changes) => { void run(() => prelaunch.update(projectId, editing.id, { expected: editableFields(editing), changes })); }} /> : null}
      {removing ? <PromptDialog title="Remove this recorded expense" label="Reason" hint={`${removing.notes ?? removing.movement_reference} · ${money(removing.amount, removing.currency_code ?? currencyCode)}. This unconfirmed entry will leave recorded totals and remain in history. Confirmed cash is unchanged.`} confirmLabel="Remove expense" busy={busy} error={error} onCancel={() => { if (!busy) setRemoving(null); }} onSubmit={(reason) => { void run(() => prelaunch.remove(projectId, removing.id, { expected: editableFields(removing), reason })); }} /> : null}
      {reversing ? <PromptDialog title="Reverse this expense" label="Reason" hint="The original remains in history and is removed from current actual cash." confirmLabel="Reverse" busy={busy} error={error} onCancel={() => { if (!busy) setReversing(null); }} onSubmit={(reason) => { void run(() => prelaunch.reverse(projectId, reversing, reason)); }} /> : null}
    </div>
  );
}

function ExpenseDialog({ initial, currencyId, currencyCode, busy, error, onCancel, onSubmit }: { initial?: PreLaunchExpense; currencyId: string; currencyCode: string | null; busy: boolean; error: string | null; onCancel: () => void; onSubmit: (body: Record<string, unknown>) => void }) {
  const [category, setCategory] = useState<string>(initial?.category ?? "permits");
  const [description, setDescription] = useState(initial?.notes ?? "");
  const [amount, setAmount] = useState(initial?.amount ?? "");
  const [date, setDate] = useState(initial?.movement_date ?? "");
  const [counterparty, setCounterparty] = useState(initial?.counterparty_reference ?? "");
  const [reference, setReference] = useState(initial?.invoice_reference ?? "");
  const [evidence, setEvidence] = useState(initial?.evidence_reference ?? "");
  const dirty = category !== (initial?.category ?? "permits") || description !== (initial?.notes ?? "") || amount !== (initial?.amount ?? "") || date !== (initial?.movement_date ?? "") || counterparty !== (initial?.counterparty_reference ?? "") || reference !== (initial?.invoice_reference ?? "") || evidence !== (initial?.evidence_reference ?? "");
  const submit = () => onSubmit({ category, amount, movement_date: date, ...(initial ? {} : { currency_id: currencyId }), counterparty_reference: counterparty || null, invoice_reference: reference || null, evidence_reference: evidence || null, notes: description });
  return <RecordPage title={initial ? "Edit Pre-Launch expense" : "Add Pre-Launch expense"} eyebrow="Pre-Launch" subtitle="Record an expense and its payment evidence" onClose={onCancel}><DraftBoundary dirty={dirty} busy={busy}><form onSubmit={event => { event.preventDefault(); if (!busy && description.trim() && amount && date) submit(); }}>
    <p className="footnote">This records an entry. It becomes cash after confirmation. Master Administrator / Boss may self-confirm; other users need a different authorised confirmer.</p>
    {error ? <Notice tone="error">{error}</Notice> : null}
    <FormSection title="Expense"><Field label="Description / notes"><input className="input" required maxLength={2000} value={description} onChange={(event) => setDescription(event.target.value)} /></Field>
    <FieldRow><Field label="Category"><select className="input" value={category} onChange={(event) => setCategory(event.target.value)}>{CATEGORIES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></Field><Field label="Amount"><MoneyInput code={currencyCode} value={amount} onChange={setAmount} /></Field></FieldRow>
    </FormSection><FormSection title="Payment and evidence"><FieldRow><Field label="Payment / movement date"><input className="input" type="date" required value={date} onChange={(event) => setDate(event.target.value)} /></Field><Field label="Counterparty / authority" optional><input className="input" value={counterparty} onChange={(event) => setCounterparty(event.target.value)} /></Field></FieldRow>
    <FieldRow><Field label="Reference" optional><input className="input" value={reference} onChange={(event) => setReference(event.target.value)} /></Field><Field label="Evidence / proof" optional><input className="input" value={evidence} onChange={(event) => setEvidence(event.target.value)} /></Field></FieldRow>
    </FormSection>
    <FormActions><Button variant="primary" type="submit" disabled={busy || !description.trim() || !amount || !date}>{busy ? "Saving…" : initial ? "Save changes" : "Record expense"}</Button><Button data-leaves-editor disabled={busy} onClick={onCancel}>Cancel</Button></FormActions>
  </form></DraftBoundary></RecordPage>;
}
