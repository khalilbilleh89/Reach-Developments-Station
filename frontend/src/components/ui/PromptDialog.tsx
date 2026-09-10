"use client";

import { useState } from "react";

import { Button } from "./Button";
import { Notice } from "./Feedback";
import { useOverlay } from "./overlay";
import { requestFormLeave, UnsavedChangesGuard } from "./UnsavedChangesGuard";

/**
 * Ask for the one thing an action needs before it is recorded — almost always a
 * reason.
 *
 * This product asks for a reason a great deal, because most of what it records
 * is somebody's decision and an audit trail without the "why" is a list of
 * changes nobody can defend. `window.prompt` did the job and did it badly: it
 * cannot be labelled, cannot say what the reason is for, is unstyled, and is
 * silently disabled in several embedded browsers — which turns a refused
 * clearance into a button that appears to do nothing.
 *
 * Modal behaviour comes from `useOverlay`: focus lands in the input, stays
 * inside while open, Escape closes this dialog only — never the drawer under
 * it — and focus returns to the action that opened it.
 */
export function PromptDialog({
  title,
  description,
  label,
  hint,
  confirmLabel = "Record",
  required = true,
  busy,
  error,
  onRefresh,
  onSubmit,
  onCancel,
}: {
  title: string;
  /** What the reason is for, in a sentence, where the title alone would not say. */
  description?: string;
  label: string;
  hint?: string;
  confirmLabel?: string;
  required?: boolean;
  busy?: boolean;
  error?: string | null;
  onRefresh?: () => void;
  onSubmit: (value: string) => void;
  onCancel: () => void;
}) {
  const [value, setValue] = useState("");
  const dialog = useOverlay<HTMLFormElement>(element => requestFormLeave(element, onCancel), "input");
  function close() { requestFormLeave(dialog.current, onCancel); }

  return (
    <div
      className="dialog-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) close();
      }}
    >
      <form
        className="dialog"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        ref={dialog}
        data-draft-boundary
        onSubmit={(event) => {
          event.preventDefault();
          if (!busy) onSubmit(value.trim());
        }}
      >
        <UnsavedChangesGuard dirty={value !== ""} busy={busy} form={dialog} />
        <h2 className="dialog-title">{title}</h2>
        {description ? <p className="dialog-description">{description}</p> : null}
        {error ? <Notice tone="error">{error}</Notice> : null}
        {onRefresh ? <Button disabled={busy} onClick={onRefresh}>Refresh current record</Button> : null}
        <label className="field">
          <span className="field-label">{label}</span>
          <input
            className="input"
            required={required}
            disabled={busy}
            value={value}
            onChange={(event) => setValue(event.target.value)}
          />
          {hint ? <span className="field-hint">{hint}</span> : null}
        </label>
        <div className="dialog-actions">
          <Button onClick={close} disabled={busy}>
            Cancel
          </Button>
          <Button variant="primary" type="submit" disabled={busy}>
            {busy ? "Working…" : confirmLabel}
          </Button>
        </div>
      </form>
    </div>
  );
}
