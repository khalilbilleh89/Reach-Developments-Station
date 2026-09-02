"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, settings } from "@/lib/api";
import type { Currency } from "@/lib/api";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Field,
  FieldRow,
  FormActions,
  Loading,
  Notice,
  TableScroll,
} from "@/components/ui";

/**
 * The currencies this business actually transacts in.
 *
 * A register and a small form, and deliberately no exchange rate anywhere: a
 * currency here is a denomination that records can carry, never a number that
 * converts one into another.
 */
export function CurrenciesSection() {
  const [rows, setRows] = useState<Currency[] | null>(null);
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ code: "", name: "", symbol: "", minor_units: "2" });
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setRows(await settings.currencies());
      setError(null);
    } catch (caught) {
      setRows([]);
      setError(caught instanceof ApiError ? caught.message : "Could not load currencies.");
    }
  }, []);

  useEffect(() => {
    void (async () => {
      await load();
    })();
  }, [load]);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await settings.createCurrency({
        code: form.code.trim().toUpperCase(),
        name: form.name.trim(),
        symbol: form.symbol.trim() || null,
        minor_units: Number(form.minor_units || "2"),
      });
      setNotice(`${form.code.trim().toUpperCase()} added.`);
      setForm({ code: "", name: "", symbol: "", minor_units: "2" });
      setAdding(false);
      await load();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "The currency could not be saved.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="stack">
      {error ? <Notice tone="error">{error}</Notice> : null}
      {notice ? <Notice tone="success">{notice}</Notice> : null}

      {adding ? (
        <Card title="Add a currency">
          <form onSubmit={submit}>
            <FieldRow columns={4}>
              <Field label="Code" hint="ISO 4217, three letters.">
                <input
                  className="input"
                  required
                  minLength={3}
                  maxLength={3}
                  value={form.code}
                  onChange={(event) => setForm({ ...form, code: event.target.value })}
                />
              </Field>
              <Field label="Name">
                <input
                  className="input"
                  required
                  value={form.name}
                  onChange={(event) => setForm({ ...form, name: event.target.value })}
                />
              </Field>
              <Field label="Symbol" optional>
                <input
                  className="input"
                  maxLength={8}
                  value={form.symbol}
                  onChange={(event) => setForm({ ...form, symbol: event.target.value })}
                />
              </Field>
              <Field label="Minor units" hint="Decimal places: 2 for USD, 3 for JOD.">
                <input
                  className="input"
                  type="number"
                  min={0}
                  max={6}
                  value={form.minor_units}
                  onChange={(event) => setForm({ ...form, minor_units: event.target.value })}
                />
              </Field>
            </FieldRow>
            <FormActions>
              <Button variant="primary" type="submit" disabled={busy}>
                {busy ? "Saving…" : "Add currency"}
              </Button>
              <Button onClick={() => setAdding(false)} disabled={busy}>
                Cancel
              </Button>
            </FormActions>
          </form>
        </Card>
      ) : null}

      <Card
        title="Currencies"
        description="Each one is a denomination records can carry. No exchange rate is stored anywhere."
        actions={
          adding ? undefined : (
            <Button variant="primary" onClick={() => setAdding(true)}>
              Add currency
            </Button>
          )
        }
        flush
      >
        {rows === null ? (
          <Loading label="Loading currencies…" shape="rows" rows={3} />
        ) : rows.length === 0 ? (
          <div className="card-body">
            <EmptyState
              title="No currencies yet"
              hint="Add one before creating a country pack: every project carries a base currency."
            />
          </div>
        ) : (
          <TableScroll label="Currencies">
            <thead>
              <tr>
                <th scope="col">Code</th>
                <th scope="col">Name</th>
                <th scope="col">Symbol</th>
                <th scope="col" className="num">
                  Minor units
                </th>
                <th scope="col">State</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((currency) => (
                <tr key={currency.id}>
                  <th scope="row" className="mono">
                    {currency.code}
                  </th>
                  <td>{currency.name}</td>
                  <td>{currency.symbol ?? "—"}</td>
                  <td className="num">{currency.minor_units}</td>
                  <td>
                    {currency.is_active ? (
                      <Badge tone="success">Active</Badge>
                    ) : (
                      <Badge tone="muted">Inactive</Badge>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </TableScroll>
        )}
      </Card>
    </div>
  );
}
