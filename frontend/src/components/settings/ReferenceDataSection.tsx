"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, settings } from "@/lib/api";
import type { CountryPack, ReferenceValue } from "@/lib/api";
import {
  Badge,
  Button,
  EmptyState,
  Field,
  Loading,
  Notice,
  Panel,
  TableScroll,
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
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [valueList, packList] = await Promise.all([
        settings.referenceValues(),
        settings.countryPacks(),
      ]);
      setValues(valueList);
      setPacks(packList);
      setError(null);
    } catch (caught) {
      setValues([]);
      setError(caught instanceof ApiError ? caught.message : "Could not load reference values.");
    }
  }, []);

  useEffect(() => {
    // Wrapped rather than called directly: the effect body must not invoke a
    // state-setting function synchronously (react-hooks/set-state-in-effect).
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

  if (values === null) return <Loading label="Loading reference data…" />;

  const packName = (id: string | null) =>
    id ? (packs.find((pack) => pack.id === id)?.country_code ?? "—") : "Global";

  return (
    <Panel
      title="Reference data"
      description="Configurable lookup values, either global or scoped to one country."
    >
      {error ? <Notice tone="error">{error}</Notice> : null}
      {notice ? <Notice tone="success">{notice}</Notice> : null}

      <form
        className="form-inline"
        onSubmit={(event) => {
          event.preventDefault();
          const form = event.currentTarget;
          const data = new FormData(form);
          void act(async () => {
            await settings.createReferenceValue({
              country_pack_id: String(data.get("country_pack_id") ?? "") || null,
              category: String(data.get("category") ?? ""),
              code: String(data.get("code") ?? ""),
              label: String(data.get("label") ?? ""),
              description: String(data.get("description") ?? "") || null,
              sort_order: Number(data.get("sort_order") ?? 0),
            });
            form.reset();
          }, "Reference value added.");
        }}
      >
        <Field label="Scope">
          <select className="input" name="country_pack_id" defaultValue="">
            <option value="">Global</option>
            {packs.map((pack) => (
              <option key={pack.id} value={pack.id}>
                {pack.country_code} · {pack.name}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Category">
          <input className="input" name="category" required placeholder="permit_type" />
        </Field>
        <Field label="Code">
          <input className="input input-short" name="code" required />
        </Field>
        <Field label="Label">
          <input className="input" name="label" required />
        </Field>
        <Field label="Order">
          <input className="input input-short" name="sort_order" type="number" min={0} defaultValue={0} />
        </Field>
        <Button variant="primary" type="submit" disabled={busy}>
          Add
        </Button>
      </form>

      {values.length === 0 ? (
        <EmptyState
          title="No reference values yet"
          hint="Add the lookup lists the business actually uses, such as permit types or legal stages."
        />
      ) : (
        <TableScroll label="Reference values">
            <thead>
              <tr>
                <th scope="col">Scope</th>
                <th scope="col">Category</th>
                <th scope="col">Code</th>
                <th scope="col">Label</th>
                <th scope="col">Status</th>
                <th scope="col">Actions</th>
              </tr>
            </thead>
            <tbody>
              {values.map((value) => (
                <tr key={value.id}>
                  <td>{packName(value.country_pack_id)}</td>
                  <td className="mono">{value.category}</td>
                  <td className="mono">{value.code}</td>
                  <td>{value.label}</td>
                  <td>
                    {value.is_active ? (
                      <Badge tone="success">Active</Badge>
                    ) : (
                      <Badge tone="muted">Retired</Badge>
                    )}
                  </td>
                  <td>
                    <Button
                      small
                      disabled={busy}
                      onClick={() =>
                        void act(
                          () =>
                            settings.updateReferenceValue(value.id, {
                              is_active: !value.is_active,
                            }),
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
    </Panel>
  );
}
