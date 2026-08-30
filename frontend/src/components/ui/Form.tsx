"use client";

import type { FormEvent, ReactNode } from "react";

import { Button } from "./Button";

/**
 * One labelled control.
 *
 * The label wraps the control rather than pointing at it by id, so every field
 * is clickable and nothing depends on an id staying unique across a screen that
 * renders the same form twice.
 */
export function Field({
  label,
  hint,
  children,
  grow,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
  grow?: boolean;
}) {
  return (
    <label className={grow ? "field filter-bar-grow" : "field"}>
      <span className="field-label">{label}</span>
      {children}
      {hint ? <span className="field-hint">{hint}</span> : null}
    </label>
  );
}

/**
 * The strip above a register that narrows it.
 *
 * Distinct from a form because it records nothing: changing a filter changes
 * what you are looking at, never what is true.
 */
export function FilterBar({ children, actions }: { children: ReactNode; actions?: ReactNode }) {
  return (
    <div className="filter-bar" role="search">
      {children}
      {actions ? <div className="filter-bar-actions button-row">{actions}</div> : null}
    </div>
  );
}

/** The actions that close a form. */
export function FormActions({ children }: { children: ReactNode }) {
  return <div className="form-actions">{children}</div>;
}

/**
 * Save and cancel, pinned to the bottom of a long form.
 *
 * Used where the fields run past a screen: an operator should never have to
 * scroll to find out whether their work can be saved.
 */
export function StickyActions({
  note,
  submitLabel,
  busy,
  onCancel,
}: {
  note?: string;
  submitLabel: string;
  busy?: boolean;
  onCancel?: () => void;
}) {
  return (
    <div className="sticky-actions">
      {note ? <p className="sticky-actions-note">{note}</p> : null}
      {onCancel ? (
        <Button onClick={onCancel} disabled={busy}>
          Cancel
        </Button>
      ) : null}
      <Button variant="primary" type="submit" disabled={busy}>
        {busy ? "Saving…" : submitLabel}
      </Button>
    </div>
  );
}

/** A form that does not reload the page. */
export function Form({
  className,
  onSubmit,
  children,
}: {
  className?: string;
  onSubmit: (event: FormEvent) => void;
  children: ReactNode;
}) {
  return (
    <form className={className} onSubmit={onSubmit}>
      {children}
    </form>
  );
}
