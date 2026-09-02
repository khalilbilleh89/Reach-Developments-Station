"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, settings } from "@/lib/api";
import type { CountryPack, ReferenceValue } from "@/lib/api";
import {
  Button,
  Card,
  DataToolbar,
  EmptyState,
  Field,
  FieldRow,
  FormActions,
  Loading,
  Notice,
  StatusDot,
  TableScroll,
  ToolbarFilter,
} from "@/components/ui";

/**
 * Controlled lookup values.
 *
 * A small dictionary, deliberately: this is not a custom-field system and not a
 * rules engine. Retired values stay listed because historical records still
 * point at them.
 */
export function ReferenceDataSection() {
  const [values, setValues] = useState<ReferenceValue[] | null>(null);
  const [packs, setPacks] = useState<CountryPack[]>([]);
  const [category, setCategory] = useState("");
  const [search, setSearch] = useState("");
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({
    country_pack_id: "",
    category: "",
    code: "",
    label: "",
    description: "",
    sort_order: "0",
  });
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [valueList, packList] = await Promise.all([settings.referenceValues(), settings.countryPacks()]);
      setValues(valueList);
      setPacks(packList);
      setError(null);
    } catch (caught) {
      setValues([]);
      setError(caught instanceof ApiError ? caught.message : "Could not load reference values.");
    }
  }, []);

  useEffect(() => {
    void (async () => {
      await load();
    })();
  }, [load]);

  async function act<T>(operation: () => Promise<T>, success: string) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await operation();
      setNotice(success);
      await load();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "The change could not be saved.");
    } finally {
      setBusy(false);
    }
  }

  const packName = (id: string | null) =>
    id ? (packs.find((pack) => pack.id === id)?.country_code ?? "—") : "Global";

  const categories = [...new Set((values ?? []).map((value) => value.category))].sort();
  const needle = search.trim().toLowerCase();
  const shown = (values ?? []).filter((value) => {
    if (category && value.category !== category) return false;
    if (needle && !`${value.code} ${value.label}`.toLowerCase().includes(needle)) return false;
    return true;
  });

  return (
    <div className="stack">
      {error ? <Notice tone="error">{error}</Notice> : null}
      {notice ? <Notice tone="success">{notice}</Notice> : null}

      {adding ? (
        <Card title="Add a reference value" description="A code records point at, and the label people read for it.">
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void act(async () => {
                await settings.createReferenceValue({
                  country_pack_id: form.country_pack_id || null,
                  category: form.category.trim(),
                  code: form.code.trim(),
                  label: form.label.trim(),
                  description: form.description.trim() || null,
                  sort_order: Number(form.sort_order || "0"),
                });
                setForm({ country_pack_id: "", category: "", code: "", label: "", description: "", sort_order: "0" });
                setAdding(false);
              }, "Reference value added.");
            }}
          >
            <FieldRow columns={3}>
              <Field label="Category" hint="permit_type, document_type, project_type…">
                <input
                  className="input"
                  required
                  list="reference-categories"
                  value={form.category}
                  onChange={(event) => setForm({ ...form, category: event.target.value })}
                />
                <datalist id="reference-categories">
                  {categories.map((value) => (
                    <option key={value} value={value} />
                  ))}
                </datalist>
              </Field>
              <Field label="Code" hint="Stored on records. Cannot change once used.">
                <input
                  className="input input-medium"
                  required
                  value={form.code}
                  onChange={(event) => setForm({ ...form, code: event.target.value })}
                />
              </Field>
              <Field label="Label">
                <input
                  className="input"
                  required
                  value={form.label}
                  onChange={(event) => setForm({ ...form, label: event.target.value })}
                />
              </Field>
              <Field label="Scope">
                <select
                  className="input"
                  value={form.country_pack_id}
                  onChange={(event) => setForm({ ...form, country_pack_id: event.target.value })}
                >
                  <option value="">Global</option>
                  {packs.map((pack) => (
                    <option key={pack.id} value={pack.id}>
                      {pack.country_code} · {pack.name}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Order" hint="Position in a list. Lower first.">
                <input
                  className="input input-xs"
                  type="number"
                  min={0}
                  value={form.sort_order}
                  onChange={(event) => setForm({ ...form, sort_order: event.target.value })}
                />
              </Field>
              <Field label="Description" optional>
                <input
                  className="input"
                  value={form.description}
                  onChange={(event) => setForm({ ...form, description: event.target.value })}
                />
              </Field>
            </FieldRow>
            <FormActions>
              <Button variant="primary" type="submit" disabled={busy}>
                {busy ? "Saving…" : "Add value"}
              </Button>
              <Button onClick={() => setAdding(false)} disabled={busy}>
                Cancel
              </Button>
            </FormActions>
          </form>
        </Card>
      ) : null}

      <DataToolbar
        search={{ value: search, onChange: setSearch, placeholder: "Code or label", label: "Search values" }}
        count={values ? { shown: shown.length, total: values.length, noun: "value" } : undefined}
        onReset={search || category ? () => {
          setSearch("");
          setCategory("");
        } : undefined}
        actions={
          adding ? undefined : (
            <Button variant="primary" onClick={() => setAdding(true)}>
              Add value
            </Button>
          )
        }
      >
        <ToolbarFilter label="Category">
          <select className="input" value={category} onChange={(event) => setCategory(event.target.value)}>
            <option value="">Every category</option>
            {categories.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </ToolbarFilter>
      </DataToolbar>

      <Card flush>
        {values === null ? (
          <Loading label="Loading reference data…" shape="rows" />
        ) : shown.length === 0 ? (
          <div className="card-body">
            <EmptyState
              title={values.length === 0 ? "No reference values yet" : "No value matches"}
              hint={
                values.length === 0
                  ? "Add the lookup lists the business actually uses, such as permit types or legal stages."
                  : "Widen the filter to see the rest."
              }
            />
          </div>
        ) : (
          <TableScroll label="Reference values">
            <thead>
              <tr>
                <th scope="col">Category</th>
                <th scope="col">Code</th>
                <th scope="col">Label</th>
                <th scope="col">Scope</th>
                <th scope="col" className="num">
                  Order
                </th>
                <th scope="col">State</th>
                <th scope="col">
                  <span className="visually-hidden">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {shown.map((value) => (
                <tr key={value.id}>
                  <td className="mono">{value.category}</td>
                  <th scope="row" className="mono">
                    {value.code}
                  </th>
                  <td>
                    {value.label}
                    {value.description ? <span className="cell-secondary">{value.description}</span> : null}
                  </td>
                  <td>{packName(value.country_pack_id)}</td>
                  <td className="num">{value.sort_order}</td>
                  <td>
                    {value.is_active ? (
                      <StatusDot tone="success">Active</StatusDot>
                    ) : (
                      <StatusDot tone="muted">Retired</StatusDot>
                    )}
                  </td>
                  <td>
                    <Button
                      small
                      variant="quiet"
                      disabled={busy}
                      onClick={() =>
                        void act(
                          () => settings.updateReferenceValue(value.id, { is_active: !value.is_active }),
                          value.is_active ? "Value retired." : "Value restored.",
                        )
                      }
                    >
                      {value.is_active ? "Retire" : "Restore"}
                    </Button>
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
