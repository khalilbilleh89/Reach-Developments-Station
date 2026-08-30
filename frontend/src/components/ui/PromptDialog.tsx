"use client";

import { useEffect, useRef, useState } from "react";

import { Button } from "./Button";

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
 */
export function PromptDialog({
  title,
  label,
  hint,
  confirmLabel = "Record",
  required = true,
  busy,
  onSubmit,
  onCancel,
}: {
  title: string;
  label: string;
  hint?: string;
  confirmLabel?: string;
  required?: boolean;
  busy?: boolean;
  onSubmit: (value: string) => void;
  onCancel: () => void;
}) {
  const [value, setValue] = useState("");
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    input.current?.focus();
  }, []);

  return (
    <div
      className="dialog-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onCancel();
      }}
    >
      <form
        className="dialog"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onKeyDown={(event) => {
          if (event.key === "Escape") onCancel();
        }}
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit(value.trim());
        }}
      >
        <h2 className="dialog-title">{title}</h2>
        <label className="field">
          <span className="field-label">{label}</span>
          <input
            ref={input}
            className="input"
            required={required}
            value={value}
            onChange={(event) => setValue(event.target.value)}
          />
          {hint ? <span className="field-hint">{hint}</span> : null}
        </label>
        <div className="dialog-actions">
          <Button onClick={onCancel} disabled={busy}>
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
