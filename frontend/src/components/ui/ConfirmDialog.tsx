"use client";

import { Button } from "./Button";
import { useOverlay } from "./overlay";

/**
 * The one confirmation.
 *
 * Reserved for something that cannot be undone from the interface — cancelling
 * a contract, revoking access. Everything reversible just happens, because a
 * dialog in front of a reversible action teaches people to dismiss dialogs.
 *
 * Modal behaviour comes from `useOverlay`: focus lands on the safe button
 * ("Keep it", the first control), stays inside while open, Escape closes this
 * dialog only, and focus returns to whatever opened it.
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
  const dialog = useOverlay<HTMLDivElement>(onCancel);

  return (
    <div
      className="dialog-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onCancel();
      }}
    >
      <div className="dialog" role="alertdialog" aria-modal="true" aria-label={title} ref={dialog}>
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
