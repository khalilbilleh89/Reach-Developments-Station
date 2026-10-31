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
  DataToolbar,
  DensitySwitch,
  EmptyState,
  Field,
  FieldRow,
  FilterChips,
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
  Segmented,
  SortHeader,
  Switch,
  TableScroll,
  ToolbarFilter,
  Tooltip,
  useSort,
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
  ["other", "Other development expense"],
] as const;

const categoryLabel = (key: string) => CATEGORIES.find(([value]) => value === key)?.[1] ?? key;
const standingLabel = (row: PreLaunchExpense) => row.removed_without_confirmation ? "Removed" : row.status === "confirmed" ? "Confirmed" : row.status === "reversed" ? "Reversed" : "Recorded";

/** What each schedule column sorts by: the server's own value, only compared. */
function readExpenseColumn(row: PreLaunchExpense, column: string): string | null {
  switch (column) {
    case "notes": return row.notes ?? row.movement_reference;
    case "category": return categoryLabel(row.category);
    case "counterparty": return row.counterparty_reference;
    case "date": return row.movement_date;
    case "total": return row.amount;
    case "status": return standingLabel(row);
    default: return null;
  }
}
const statusTone = (status: string): Tone =>
  status === "confirmed" ? "success" : status === "reversed" ? "muted" : "warning";

const editableFields = (row: PreLaunchExpense) => ({
  amount_ex_vat: row.amount_ex_vat ?? null, vat_rate_percent: row.vat_rate_percent ?? null,
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
  // The register arrives whole, so the schedule may be ordered by what it already shows.
  const { sort, toggle, sorted } = useSort(expenses, readExpenseColumn);
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
      setReadError(caught instanceof ApiError ? caught.message : "Could not load Authorities expenses.");
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
        title="Authorities"
        subtitle={sectionDescription("prelaunch")}
        actions={canRecord ? <Button variant="primary" onClick={() => setAdding(true)}>Add expense</Button> : undefined}
      />
      {error ? <Notice tone="error">{error}</Notice> : null}
      {readError ? <><Notice tone="error">{readError}</Notice><Button disabled={retrying} onClick={() => void load()}>{retrying ? "Retrying…" : "Retry Authorities expenses"}</Button></> : null}
      {register ? (
        <Card tone="command" title="Expense position"><Position compact>
          <PositionFigure label="Recorded amount" value={money(register.recorded_amount, currencyCode)} note="Not confirmed cash" />
          <PositionFigure lead label="Confirmed paid amount" value={money(register.confirmed_paid_amount, currencyCode)} note="Total including VAT; included once in project cashflow" />
        </Position><p className="footnote">Recorded means entered but not yet confirmed as cash. A different authorised Finance or CFO user confirms payment. Master Administrator / Boss can confirm their own expenses.</p></Card>
      ) : null}
      <div className="prelaunch-ledger-layout">
      <Card title="Expense register" description="Search notes, counterparties, references or categories. Filters apply to the register; position totals remain project-wide." actions={<Segmented label="Expense presentation" value={schedule ? "schedule" : "entries"} onChange={value => setSchedule(value === "schedule")} options={[{ value: "entries", label: "Entries" }, { value: "schedule", label: "Schedule" }]} />}>
        <DataToolbar search={{ value: search, onChange: setSearch, label: "Search expenses", placeholder: "Notes, counterparty, reference or category" }} actions={schedule ? <DensitySwitch /> : undefined}>
          <ToolbarFilter label="Expense status" active={status !== ""}><select className="input" value={status} onChange={event => setStatus(event.target.value)}><option value="">All statuses</option><option value="recorded">Recorded</option><option value="confirmed">Confirmed</option><option value="reversed">Reversed</option><option value="removed">Removed</option></select></ToolbarFilter>
        </DataToolbar>
        <FilterChips chips={[
          ...(status ? [{ key: "status", label: `Status: ${status.charAt(0).toUpperCase()}${status.slice(1)}`, onRemove: () => setStatus("") }] : []),
          ...(search ? [{ key: "search", label: `“${search}”`, onRemove: () => setSearch("") }] : []),
        ]} />
        {register ? <p className="register-result-count">{expenses.length} matching {expenses.length === 1 ? "entry" : "entries"}{search || status ? <Button small variant="link" onClick={() => { setSearch(""); setStatus(""); }}>Clear filters</Button> : null}</p> : null}
        {register === null ? readError ? null : <Loading label="Loading Authorities expenses" shape="rows" /> : register.expenses.length === 0 ? (
          <div className="card-body"><EmptyState title="No Authorities expenses" hint="Record authority, utility and other allowed development expenses here." /></div>
        ) : expenses.length === 0 ? <EmptyState title="No matching expenses" actions={<Button onClick={() => { setSearch(""); setStatus(""); }}>Reset filters</Button>} /> : (
          schedule ? <TableScroll label="Authorities expense register" fixedFirst stickyHeader>
            <thead><tr><SortHeader column="notes" sort={sort} onToggle={toggle}>Notes / reference</SortHeader><SortHeader column="category" sort={sort} onToggle={toggle}>Category</SortHeader><SortHeader column="counterparty" sort={sort} onToggle={toggle}>Counterparty / authority</SortHeader><SortHeader column="date" sort={sort} onToggle={toggle}>Date</SortHeader><SortHeader column="total" sort={sort} onToggle={toggle} className="num">Total including VAT</SortHeader><SortHeader column="status" sort={sort} onToggle={toggle}>Status</SortHeader><th scope="col">Reference</th><th scope="col"><span className="visually-hidden">Actions</span></th></tr></thead>
            <tbody>{sorted.map((row) => (
              <tr key={row.id}>
                <th scope="row" className="cell-prose">{row.notes ?? row.movement_reference}</th>
                <td>{categoryLabel(row.category)}</td>
                <td>{row.counterparty_reference ?? "—"}</td>
                <td>{businessDate(row.movement_date)}</td>
                <td className="num">{money(row.amount, row.currency_code ?? currencyCode)}<ExpenseVat row={row} currencyCode={currencyCode} /></td>
                <td><Badge tone={statusTone(row.status)}>{standingLabel(row)}</Badge>{row.reversal_reason ? <p className="footnote">{row.reversal_reason}</p> : null}</td>
                <td><span className="cell-secondary">Invoice: {row.invoice_reference ?? "—"}</span><span className="cell-secondary">Evidence: {row.evidence_reference ?? "—"}</span></td>
                <td className="cell-prose">{expenseActions(row)}</td>
              </tr>
            ))}</tbody>
          </TableScroll> : <div className="expense-entry-list">{expenses.map(row => <article className="expense-entry" key={row.id}>
            <header><div><span className="eyebrow"><Icon name="money" />{categoryLabel(row.category)}</span><h3>{row.notes ?? row.movement_reference}</h3><p className="footnote">{row.counterparty_reference ?? "Counterparty not recorded"}</p></div><div className="expense-entry-amount"><strong>{money(row.amount, row.currency_code ?? currencyCode)}</strong><ExpenseVat row={row} currencyCode={currencyCode} /><Badge tone={statusTone(row.status)}>{standingLabel(row)}</Badge></div></header>
            <dl><div><dt>Movement date</dt><dd>{businessDate(row.movement_date)}</dd></div><div><dt>Movement reference</dt><dd>{row.movement_reference}</dd></div><div><dt>Invoice reference</dt><dd>{row.invoice_reference ?? "Not recorded"}</dd></div><div><dt>Supporting evidence</dt><dd>{row.evidence_reference ?? "Not recorded"}</dd></div></dl>
            {row.reversal_reason ? <p className="footnote">{row.reversal_reason}</p> : null}<footer>{expenseActions(row)}</footer>
          </article>)}</div>
        )}
      </Card>
      {register ? <Card title="Expenses by category" description="Current recorded and confirmed expenses. Removed and reversed entries are excluded." actions={<Switch checked={showEmptyCategories} onChange={setShowEmptyCategories}>Include empty categories</Switch>}>
        <div className="expense-category-list">{register.categories.filter(category => showEmptyCategories || nonzero(category.recorded_amount) || nonzero(category.confirmed_paid_amount)).map(category => <section key={category.category}><h3>{categoryLabel(category.category)}</h3><dl><div><dt>Recorded</dt><dd>{money(category.recorded_amount, currencyCode)}</dd></div><div><dt>Confirmed paid</dt><dd>{money(category.confirmed_paid_amount, currencyCode)}</dd></div><div><dt>Total expenses</dt><dd>{money(category.total_amount, currencyCode)}</dd></div><div><dt>Share of confirmed paid</dt><dd>{nonzero(register.confirmed_paid_amount) ? category.confirmed_share_percent + "%" : "No confirmed payments"}</dd></div></dl></section>)}</div>
        <p className="footnote">Amounts include <Tooltip term="VAT">Value added tax</Tooltip> where recorded. Total expenses include unconfirmed entries; confirmed paid is the cash amount. Percentages use confirmed paid only.</p>
      </Card> : null}
      </div>
      {adding ? <ExpenseDialog projectId={projectId} currencyId={currencyId} currencyCode={currencyCode} busy={busy} error={error} onCancel={() => { if (!busy) setAdding(false); }} onSubmit={(body) => { void run(() => prelaunch.record(projectId, body)); }} /> : null}
      {editing ? <ExpenseDialog projectId={projectId} key={editing.id} initial={editing} currencyId={currencyId} currencyCode={editing.currency_code ?? currencyCode} busy={busy} error={error} onCancel={() => { if (!busy) setEditing(null); }} onSubmit={(changes) => { void run(() => prelaunch.update(projectId, editing.id, { expected: editableFields(editing), changes })); }} /> : null}
      {removing ? <PromptDialog title="Remove this recorded expense" label="Reason" hint={`${removing.notes ?? removing.movement_reference} · ${money(removing.amount, removing.currency_code ?? currencyCode)}. This unconfirmed entry will leave recorded totals and remain in history. Confirmed cash is unchanged.`} confirmLabel="Remove expense" busy={busy} error={error} onCancel={() => { if (!busy) setRemoving(null); }} onSubmit={(reason) => { void run(() => prelaunch.remove(projectId, removing.id, { expected: editableFields(removing), reason })); }} /> : null}
      {reversing ? <PromptDialog title="Reverse this expense" label="Reason" hint="The original remains in history and is removed from current actual cash." confirmLabel="Reverse" busy={busy} error={error} onCancel={() => { if (!busy) setReversing(null); }} onSubmit={(reason) => { void run(() => prelaunch.reverse(projectId, reversing, reason)); }} /> : null}
    </div>
  );
}

function ExpenseVat({ row, currencyCode }: { row: PreLaunchExpense; currencyCode: string | null }) {
  return row.amount_ex_vat != null ? <p className="footnote">Excl. VAT {money(row.amount_ex_vat, row.currency_code ?? currencyCode)} · VAT {row.vat_rate_percent}%: {money(row.vat_amount, row.currency_code ?? currencyCode)}</p> : <p className="footnote">VAT breakdown not recorded</p>;
}

function ExpenseDialog({ projectId, initial, currencyId, currencyCode, busy, error, onCancel, onSubmit }: { projectId: string; initial?: PreLaunchExpense; currencyId: string; currencyCode: string | null; busy: boolean; error: string | null; onCancel: () => void; onSubmit: (body: Record<string, unknown>) => void }) {
  const [category, setCategory] = useState<string>(initial?.category ?? "permits");
  const [notes, setNotes] = useState(initial?.notes ?? "");
  const [amount, setAmount] = useState(initial?.amount_ex_vat ?? initial?.amount ?? "");
  const [vatRate, setVatRate] = useState(initial?.vat_rate_percent ?? "");
  const [legacyTotal, setLegacyTotal] = useState(!!initial && initial.amount_ex_vat == null);
  const [result, setResult] = useState<{ key: string; value: import("@/lib/api/types").PreLaunchAmount } | null>(null);
  const [failure, setFailure] = useState<{ key: string; message: string } | null>(null);
  const [retry, setRetry] = useState(0);
  const previewKey = JSON.stringify([projectId, amount, vatRate, legacyTotal, retry]);
  useEffect(() => {
    let active = true;
    if (!amount) return;
    const timer = setTimeout(() => {
      const body = legacyTotal ? { amount } : { amount_ex_vat: amount, vat_rate_percent: vatRate || "0" };
      void prelaunch.preview(projectId, body).then(value => { if (active) { setResult({ key: previewKey, value }); setFailure(null); } })
        .catch(caught => { if (active) setFailure({ key: previewKey, message: caught instanceof ApiError ? caught.message : "Could not calculate the expense total." }); });
    }, 250);
    return () => { active = false; clearTimeout(timer); };
  }, [projectId, amount, vatRate, legacyTotal, previewKey]);
  const preview = result?.key === previewKey ? result.value : null;
  const previewError = failure?.key === previewKey ? failure.message : null;
  const [date, setDate] = useState(initial?.movement_date ?? "");
  const [counterparty, setCounterparty] = useState(initial?.counterparty_reference ?? "");
  const [reference, setReference] = useState(initial?.invoice_reference ?? "");
  const [evidence, setEvidence] = useState(initial?.evidence_reference ?? "");
  const dirty = category !== (initial?.category ?? "permits") || notes !== (initial?.notes ?? "") || amount !== (initial?.amount_ex_vat ?? initial?.amount ?? "") || vatRate !== (initial?.vat_rate_percent ?? "") || legacyTotal !== (!!initial && initial.amount_ex_vat == null) || date !== (initial?.movement_date ?? "") || counterparty !== (initial?.counterparty_reference ?? "") || reference !== (initial?.invoice_reference ?? "") || evidence !== (initial?.evidence_reference ?? "");
  const submit = () => onSubmit({ category, ...(legacyTotal ? { amount } : { amount_ex_vat: amount, vat_rate_percent: vatRate || "0" }), movement_date: date, ...(initial ? {} : { currency_id: currencyId }), counterparty_reference: counterparty || null, invoice_reference: reference || null, evidence_reference: evidence || null, notes: notes.trim() || null });
  return <RecordPage title={initial ? "Edit Authorities expense" : "Add Authorities expense"} eyebrow="Authorities" subtitle="Record an expense and its payment evidence" onClose={onCancel}><DraftBoundary dirty={dirty} busy={busy}><form onSubmit={event => { event.preventDefault(); if (!busy && amount && date && preview) submit(); }}>
    <p className="footnote">This records an entry. It becomes cash after confirmation. Master Administrator / Boss may self-confirm; other users need a different authorised confirmer.</p>
    {error ? <Notice tone="error">{error}</Notice> : null}
    <FormSection title="Expense"><Field label="Notes" optional hint="Add any extra details about this expense, or leave blank."><textarea className="input" maxLength={2000} value={notes} onChange={(event) => setNotes(event.target.value)} /></Field>
    <FieldRow><Field label="Category"><select className="input" value={category} onChange={(event) => setCategory(event.target.value)}>{CATEGORIES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></Field><Field label={legacyTotal ? "Existing total (VAT breakdown unknown)" : "Amount excluding VAT"}><MoneyInput code={currencyCode} value={amount} onChange={setAmount} /></Field></FieldRow>
    {legacyTotal ? <Notice tone="info">This entry has no recorded VAT breakdown. Its total is preserved. <Button onClick={() => { setLegacyTotal(false); setAmount(""); }}>Enter VAT breakdown</Button></Notice> : <Field label="VAT (%)" optional hint="Leave blank or enter 0 when VAT does not apply."><input className="input" type="number" min="0" max="100" step="0.0001" value={vatRate} onChange={event => setVatRate(event.target.value)} /></Field>}
    {previewError ? <Notice tone="error">{previewError} <Button onClick={() => setRetry(retry + 1)}>Retry total</Button></Notice> : preview ? <Position compact><PositionFigure label="VAT amount" value={preview.vat_amount == null ? "Not recorded" : money(preview.vat_amount, currencyCode)} /><PositionFigure lead label="Total including VAT" value={money(preview.amount, currencyCode)} /></Position> : amount ? <Loading label="Calculating expense total" /> : null}
    </FormSection><FormSection title="Payment and evidence"><FieldRow><Field label="Payment / movement date"><input className="input" type="date" required value={date} onChange={(event) => setDate(event.target.value)} /></Field><Field label="Counterparty / authority" optional><input className="input" value={counterparty} onChange={(event) => setCounterparty(event.target.value)} /></Field></FieldRow>
    <FieldRow><Field label="Reference" optional><input className="input" value={reference} onChange={(event) => setReference(event.target.value)} /></Field><Field label="Evidence / proof" optional><input className="input" value={evidence} onChange={(event) => setEvidence(event.target.value)} /></Field></FieldRow>
    </FormSection>
    <FormActions><Button variant="primary" type="submit" disabled={busy || !amount || !date || !preview}>{busy ? "Saving…" : initial ? "Save changes" : "Record expense"}</Button><Button data-leaves-editor disabled={busy} onClick={onCancel}>Cancel</Button></FormActions>
  </form></DraftBoundary></RecordPage>;
}
