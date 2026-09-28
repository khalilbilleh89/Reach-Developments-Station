"use client";

import { useState } from "react";

import {
  Badge,
  Button,
  Card,
  DataToolbar,
  EmptyState,
  Field,
  FieldRow,
  FormDialog,
  Loading,
  Notice,
  PromptDialog,
  TableScroll,
} from "@/components/ui";
import { useAnswer } from "@/lib/answer";
import { ApiError, settings } from "@/lib/api";
import type { Currency } from "@/lib/api";

const EMPTY_DRAFT = { code: "", name: "", symbol: "", minor_units: "2" };

function message(caught: unknown): string {
  return caught instanceof ApiError ? caught.message : "The currency change could not be saved.";
}

/** System Administrator ownership of the shared currency registry. */
export function CurrencySection() {
  const answer = useAnswer(true, settings.currencies, []);
  const [search, setSearch] = useState("");
  const [draft, setDraft] = useState(EMPTY_DRAFT);
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<Currency | null>(null);
  const [symbol, setSymbol] = useState("");
  const [removing, setRemoving] = useState<Currency | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const rows = answer.status === "ready" ? answer.data : [];
  const needle = search.trim().toLowerCase();
  const shown = rows.filter(currency =>
    !needle || currency.code.toLowerCase().includes(needle) ||
    currency.name.toLowerCase().includes(needle),
  );

  async function create(): Promise<void> {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await settings.createCurrency({
        code: draft.code,
        name: draft.name,
        symbol: draft.symbol.trim() || null,
        minor_units: Number(draft.minor_units),
      });
      setDraft(EMPTY_DRAFT);
      setAdding(false);
      setNotice("Currency created.");
      answer.retry();
    } catch (caught) {
      setError(message(caught));
    } finally {
      setBusy(false);
    }
  }

  async function saveSymbol(): Promise<void> {
    if (!editing) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await settings.updateCurrency(editing.id, { symbol: symbol.trim() || null });
      setEditing(null);
      setNotice("Currency symbol updated across the shared registry.");
      answer.retry();
    } catch (caught) {
      setError(message(caught));
    } finally {
      setBusy(false);
    }
  }

  async function remove(reason: string): Promise<void> {
    if (!removing) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await settings.deleteCurrency(removing.id, reason);
      setNotice(`${removing.code} deleted.`);
      setRemoving(null);
      answer.retry();
    } catch (caught) {
      setError(message(caught));
    } finally {
      setBusy(false);
    }
  }

  const minorUnits = Number(draft.minor_units);
  const invalidDraft = draft.code.trim().length !== 3 || !draft.name.trim() ||
    !Number.isInteger(minorUnits) || minorUnits < 0 || minorUnits > 6;

  return (
    <div className="stack">
      <Notice tone="info">
        Currency symbols are shared display metadata. Editing one does not convert or
        recalculate any amount; financial screens continue to identify amounts by currency code.
      </Notice>
      {error && !adding && !editing && !removing ? <Notice tone="error">{error}</Notice> : null}
      {notice ? <Notice tone="success">{notice}</Notice> : null}

      <DataToolbar
        framed
        search={{ value: search, onChange: setSearch, placeholder: "Code or name", label: "Search currencies" }}
        count={answer.status === "ready" ? { shown: shown.length, total: rows.length, noun: "currency" } : undefined}
        actions={<Button variant="primary" onClick={() => { setError(null); setAdding(true); }}>Add currency</Button>}
      />

      <Card flush>
        {answer.status === "loading" ? <Loading label="Loading currencies…" shape="rows" /> : null}
        {answer.status === "failed" ? (
          <div className="card-body"><Notice tone="error">{answer.message}</Notice><Button onClick={answer.retry}>Try again</Button></div>
        ) : null}
        {answer.status === "ready" && shown.length === 0 ? (
          <div className="card-body"><EmptyState title={rows.length ? "No currency matches" : "No currencies configured"} /></div>
        ) : null}
        {answer.status === "ready" && shown.length ? (
          <TableScroll fixedFirst label="Currency registry">
            <thead><tr><th scope="col">Currency</th><th scope="col">Symbol</th><th scope="col">Minor units</th><th scope="col">Status</th><th scope="col"><span className="visually-hidden">Actions</span></th></tr></thead>
            <tbody>{shown.map(currency => (
              <tr key={currency.id}>
                <th scope="row"><strong>{currency.code}</strong><span className="cell-subtitle">{currency.name}</span></th>
                <td>{currency.symbol ?? "—"}</td>
                <td className="figure">{currency.minor_units}</td>
                <td><Badge tone={currency.is_active ? "success" : "neutral"}>{currency.is_active ? "Active" : "Inactive"}</Badge></td>
                <td><div className="button-row"><Button small onClick={() => { setError(null); setSymbol(currency.symbol ?? ""); setEditing(currency); }}>Edit symbol</Button><Button small variant="danger" onClick={() => { setError(null); setRemoving(currency); }}>Delete</Button></div></td>
              </tr>
            ))}</tbody>
          </TableScroll>
        ) : null}
      </Card>

      {adding ? (
        <FormDialog title="Add currency" description="Creates shared configuration. Currency codes cannot be changed later." confirmLabel="Create currency" busy={busy} disabled={invalidDraft} onCancel={() => { if (!busy) setAdding(false); }} onSubmit={() => void create()}>
          {error ? <Notice tone="error">{error}</Notice> : null}
          <FieldRow columns={2}>
            <Field label="Currency code" hint="Three letters, such as USD or JOD."><input className="input input-short" required minLength={3} maxLength={3} value={draft.code} onChange={event => setDraft({ ...draft, code: event.target.value.toUpperCase() })} /></Field>
            <Field label="Name"><input className="input" required maxLength={120} value={draft.name} onChange={event => setDraft({ ...draft, name: event.target.value })} /></Field>
            <Field label="Symbol" optional><input className="input input-short" maxLength={8} value={draft.symbol} onChange={event => setDraft({ ...draft, symbol: event.target.value })} /></Field>
            <Field label="Minor units" hint="Decimal places used by this currency."><input className="input input-short" type="number" required min={0} max={6} step={1} value={draft.minor_units} onChange={event => setDraft({ ...draft, minor_units: event.target.value })} /></Field>
          </FieldRow>
        </FormDialog>
      ) : null}

      {editing ? (
        <FormDialog title={`Edit ${editing.code} symbol`} description="This changes the stored display symbol only. Numeric amounts and their currency codes remain unchanged." confirmLabel="Save symbol" busy={busy} onCancel={() => { if (!busy) setEditing(null); }} onSubmit={() => void saveSymbol()}>
          {error ? <Notice tone="error">{error}</Notice> : null}
          <Field label="Symbol" optional hint="Leave blank to display the currency code without a symbol."><input className="input input-short" maxLength={8} value={symbol} onChange={event => setSymbol(event.target.value)} /></Field>
        </FormDialog>
      ) : null}

      {removing ? (
        <PromptDialog title={`Delete ${removing.code}?`} description="This permanently removes the unused currency. Any country configuration, project or business record that still references it will block deletion. Use inactive status when history must remain." label="Reason for deletion" hint="At least eight characters. The reason and previous currency details remain in audit history." confirmLabel="Delete currency" destructive busy={busy} error={error} onCancel={() => { if (!busy) setRemoving(null); }} onSubmit={reason => void remove(reason)} />
      ) : null}
    </div>
  );
}
