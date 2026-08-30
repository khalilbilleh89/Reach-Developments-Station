"use client";

import { useState } from "react";

import { ApiError } from "@/lib/api";
import { Button, Field, FormActions, Notice } from "@/components/ui";

/**
 * One field in an edit form, described rather than hand-written each time.
 *
 * Deliberately a plain description, not a form framework: there is no schema
 * language, no validation engine and no registry. The backend remains the
 * authority on what is legal — this only decides what is rendered.
 */
export type EditField = {
  name: string;
  label: string;
  hint?: string;
  kind?: "text" | "number" | "date" | "checkbox" | "select" | "textarea";
  options?: { value: string; label: string }[];
  /** Hidden entirely when false — used where the caller may not see a value. */
  visible?: boolean;
};

export type EditValues = Record<string, string | boolean | null>;

/**
 * A compact Save/Cancel form over a described set of fields.
 *
 * Only fields the user actually changed are sent, so a PATCH says what it
 * means: omitted leaves the column alone, an emptied optional field clears it.
 * Immutable fields are simply never described here, so they cannot be sent —
 * the API now rejects unknown and prohibited keys outright.
 */
export function EditForm({
  fields,
  initial,
  onSave,
  onCancel,
  submitLabel = "Save changes",
}: {
  fields: EditField[];
  initial: EditValues;
  onSave: (changes: Record<string, unknown>) => Promise<void>;
  onCancel: () => void;
  submitLabel?: string;
}) {
  const [values, setValues] = useState<EditValues>(initial);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const set = (name: string, value: string | boolean) =>
    setValues((current) => ({ ...current, [name]: value }));

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const changes: Record<string, unknown> = {};
      for (const field of fields) {
        if (field.visible === false) continue;
        const next = values[field.name];
        const previous = initial[field.name];
        if (next === previous) continue;
        // An emptied optional text field means "clear this", which the API
        // reads as an explicit null rather than as an omission.
        changes[field.name] = next === "" ? null : next;
      }
      if (Object.keys(changes).length > 0) await onSave(changes);
      onCancel();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not save the changes.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit}>
      {error ? <Notice tone="error">{error}</Notice> : null}
      <div className="form-grid form-grid-3">
        {fields
          .filter((field) => field.visible !== false)
          .map((field) => {
            const value = values[field.name];
            if (field.kind === "checkbox") {
              return (
                <label className="checkbox" key={field.name}>
                  <input
                    type="checkbox"
                    checked={Boolean(value)}
                    onChange={(event) => set(field.name, event.target.checked)}
                  />
                  <span>{field.label}</span>
                </label>
              );
            }
            return (
              <Field key={field.name} label={field.label} hint={field.hint}>
                {field.kind === "select" ? (
                  <select
                    className="input"
                    value={String(value ?? "")}
                    onChange={(event) => set(field.name, event.target.value)}
                  >
                    {(field.options ?? []).map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                ) : field.kind === "textarea" ? (
                  <textarea
                    className="input"
                    rows={2}
                    value={String(value ?? "")}
                    onChange={(event) => set(field.name, event.target.value)}
                  />
                ) : (
                  <input
                    className={field.kind === "date" ? "input input-short" : "input"}
                    type={field.kind === "date" ? "date" : "text"}
                    inputMode={field.kind === "number" ? "decimal" : undefined}
                    value={String(value ?? "")}
                    onChange={(event) => set(field.name, event.target.value)}
                  />
                )}
              </Field>
            );
          })}
        <FormActions>
          <Button variant="primary" type="submit" disabled={busy}>
            {busy ? "Saving…" : submitLabel}
          </Button>
          <Button onClick={onCancel} disabled={busy}>
            Cancel
          </Button>
        </FormActions>
      </div>
    </form>
  );
}

/** Turn a nullable API value into something an input can hold. */
export function asValue(value: string | number | boolean | null | undefined): string | boolean {
  if (typeof value === "boolean") return value;
  if (value === null || value === undefined) return "";
  return String(value);
}
