"use client";

import type { ReactNode } from "react";

import { DialogPortal } from "./DialogPortal";
import { Button } from "./Button";
import { useOverlay } from "./overlay";
import { requestFormLeave, UnsavedChangesGuard } from "./UnsavedChangesGuard";
import { useFormDirty } from "./useFormDirty";

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
 * page beneath it, and focus returns to whatever opened it.
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
  const dialog = useOverlay<HTMLFormElement>(element => requestFormLeave(element, onCancel), "input");
  function close() { requestFormLeave(dialog.current, onCancel); }
  const dirty = useFormDirty(dialog);

  return (
    <DialogPortal><div
      className="dialog-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) close();
      }}
    >
      <form
        className="dialog dialog-wide"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        ref={dialog}
        data-draft-boundary
        onSubmit={(event) => {
          event.preventDefault();
          if (!busy && !disabled) onSubmit();
        }}
      >
        <UnsavedChangesGuard dirty={dirty} busy={busy} form={dialog} />
        <h2 className="dialog-title">{title}</h2>
        {description ? <p className="dialog-description">{description}</p> : null}
        <fieldset disabled={busy} className="draft-fields">{children}</fieldset>
        <div className="dialog-actions">
          <Button onClick={close} disabled={busy}>
            Cancel
          </Button>
          <Button variant="primary" type="submit" disabled={busy || disabled}>
            {busy ? "Working…" : confirmLabel}
          </Button>
        </div>
      </form>
    </div></DialogPortal>
  );
}
