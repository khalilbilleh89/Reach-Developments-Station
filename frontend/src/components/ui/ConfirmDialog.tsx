"use client";

import { useEffect, useRef } from "react";

import { Button } from "./Button";

/**
 * The one confirmation.
 *
 * Reserved for something that cannot be undone from the interface — cancelling
 * a contract, revoking access. Everything reversible just happens, because a
 * dialog in front of a reversible action teaches people to dismiss dialogs.
 */
export function ConfirmDialog({
  title,
  body,
  confirmLabel,
  tone = "danger",
  busy,
  onConfirm,
  onCancel,
}: {
  title: string;
  body: string;
  confirmLabel: string;
  tone?: "danger" | "primary";
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const dialogRef = useRef<HTMLDivElement>(null);

  // Focus moves into the dialog on open, so the keyboard is where the eye is
  // and Escape reaches the handler below without a click first.
  useEffect(() => {
    dialogRef.current?.querySelector("button")?.focus();
  }, []);

  return (
    <div
      className="dialog-backdrop"
      onClick={(event) => {
        if (event.target === event.currentTarget) onCancel();
      }}
    >
      <div
        className="dialog"
        ref={dialogRef}
        role="alertdialog"
        aria-modal="true"
        aria-label={title}
        onKeyDown={(event) => {
          if (event.key === "Escape") onCancel();
        }}
      >
        <h2 className="dialog-title">{title}</h2>
        <p className="dialog-body">{body}</p>
        <div className="dialog-actions">
          <Button onClick={onCancel} disabled={busy}>
            Keep it
          </Button>
          <Button
            variant={tone === "danger" ? "danger" : "primary"}
            onClick={onConfirm}
            disabled={busy}
          >
            {busy ? "Working…" : confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
