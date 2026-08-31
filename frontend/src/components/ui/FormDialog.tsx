"use client";

import type { ReactNode } from "react";

import { Button } from "./Button";
import { useOverlay } from "./overlay";

/**
 * Ask for the several things an action needs, rather than the one.
 *
 * `PromptDialog` covers the common case — a reason and nothing else. Some
 * records need more than that and are the worse for being squeezed into one
 * box: an attestation that an event occurred needs the date it occurred on,
 * the evidence, and why, and a dialog that asks only for the evidence has to
 * invent the other two. Inventing them is how a system ends up recording that
 * every contractual event happened on the day somebody got round to typing it.
 *
 * The fields are the caller's, so each dialog asks for exactly what it needs
 * and owns its own validation. Modal behaviour is the same as every other
 * overlay: focus lands inside, stays inside, Escape closes this and not the
 * drawer beneath it, and focus returns to whatever opened it.
 */
export function FormDialog({
  title,
  description,
  confirmLabel = "Record",
  busy,
  disabled,
  onSubmit,
  onCancel,
  children,
}: {
  title: string;
  description?: string;
  confirmLabel?: string;
  busy?: boolean;
  disabled?: boolean;
  onSubmit: () => void;
  onCancel: () => void;
  children: ReactNode;
}) {
  const dialog = useOverlay<HTMLFormElement>(onCancel, "input");

  return (
    <div
      className="dialog-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onCancel();
      }}
    >
      <form
        className="dialog dialog-wide"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        ref={dialog}
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit();
        }}
      >
        <h2 className="dialog-title">{title}</h2>
        {description ? <p className="dialog-description">{description}</p> : null}
        {children}
        <div className="dialog-actions">
          <Button onClick={onCancel} disabled={busy}>
            Cancel
          </Button>
          <Button variant="primary" type="submit" disabled={busy || disabled}>
            {busy ? "Working…" : confirmLabel}
          </Button>
        </div>
      </form>
    </div>
  );
}
