"use client";

import { useState } from "react";

import { ApiError } from "@/lib/api";
import { Button, Field, FieldRow, FormActions, FormSection, Notice } from "@/components/ui";

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
  /** The titled group this field sits in. Fields in the same group sit together. */
  group?: string;
  /** A unit or denomination drawn beside the control: "JOD", "sqm", "%". */
  affix?: string;
  /** How wide the control should be. Short for a number, a date, a code. */
  width?: "short" | "medium" | "full";
};

export type EditValues = Record<string, string | boolean | null>;

/**
 * A Save/Cancel form over a described set of fields.
 *
 * Only fields the user actually changed are sent, so a PATCH says what it
 * means: omitted leaves the column alone, an emptied optional field clears it.
 * Immutable fields are simply never described here, so they cannot be sent —
 * the API rejects unknown and prohibited keys outright.
 *
 * Fields are laid out in the groups the caller named, three to a row, with
 * each control sized to what it holds: a date is not a paragraph wide.
 */
export function EditForm({
  fields,
  initial,
  onSave,
  onCancel,
  submitLabel = "Save changes",
  columns = 3,
}: {
  fields: EditField[];
  initial: EditValues;
  onSave: (changes: Record<string, unknown>) => Promise<void>;
  onCancel: () => void;
  submitLabel?: string;
  columns?: 2 | 3 | 4;
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

  const shown = fields.filter((field) => field.visible !== false);
  const groups: { title: string | null; fields: EditField[] }[] = [];
  for (const field of shown) {
    const title = field.group ?? null;
    const last = groups[groups.length - 1];
    if (last && last.title === title) last.fields.push(field);
    else groups.push({ title, fields: [field] });
  }

  const control = (field: EditField) => {
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
    const width =
      field.width === "short" || field.kind === "date" || field.kind === "number"
        ? "input input-short"
        : field.width === "medium"
          ? "input input-medium"
          : "input";
    const input =
      field.kind === "select" ? (
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
      ) : field.affix ? (
        <span className="input-shell input-shell-money">
          <input
            className="input"
            inputMode={field.kind === "number" ? "decimal" : undefined}
            value={String(value ?? "")}
            onChange={(event) => set(field.name, event.target.value)}
          />
          <span className="input-affix" aria-hidden="true">
            {field.affix}
          </span>
        </span>
      ) : (
        <input
          className={width}
          type={field.kind === "date" ? "date" : "text"}
          inputMode={field.kind === "number" ? "decimal" : undefined}
          value={String(value ?? "")}
          onChange={(event) => set(field.name, event.target.value)}
        />
      );
    return (
      <Field
        key={field.name}
        label={field.label}
        hint={field.hint}
        className={field.kind === "textarea" ? "field-span-all" : undefined}
      >
        {input}
      </Field>
    );
  };

  return (
    <form onSubmit={submit}>
      {error ? <Notice tone="error">{error}</Notice> : null}
      {groups.map((group, index) =>
        group.title ? (
          <FormSection key={group.title} title={group.title}>
            <FieldRow columns={columns}>{group.fields.map(control)}</FieldRow>
          </FormSection>
        ) : (
          <FieldRow key={`group-${index}`} columns={columns}>
            {group.fields.map(control)}
          </FieldRow>
        ),
      )}
      <FormActions>
        <Button variant="primary" type="submit" disabled={busy}>
          {busy ? "Saving…" : submitLabel}
        </Button>
        <Button onClick={onCancel} disabled={busy}>
          Cancel
        </Button>
      </FormActions>
    </form>
  );
}

/** Turn a nullable API value into something an input can hold. */
export function asValue(value: string | number | boolean | null | undefined): string | boolean {
  if (typeof value === "boolean") return value;
  if (value === null || value === undefined) return "";
  return String(value);
}
