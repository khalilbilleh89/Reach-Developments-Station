"use client";

import { useState } from "react";
import { ApiError } from "@/lib/api";
import { Button, PromptDialog } from "@/components/ui";

/** The destructive action stays inside a reasoned confirmation, with recoverable errors. */
export function DeleteRecordButton({ label, onDelete, onDeleted, description }: {
  label: string;
  description?: string;
  onDelete: (reason: string) => Promise<void>;
  onDeleted: () => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return <>
    <Button variant="danger" onClick={() => { setError(null); setOpen(true); }}>Delete {label}</Button>
    {open ? <PromptDialog title={`Delete ${label}?`} label="Reason for deletion"
      description={description ?? "This permanently removes this record. Linked financial and legal history is protected. A building or floor must be empty first. The audit trail is retained."}
      confirmLabel="Delete permanently" error={error} busy={busy}
      onCancel={() => { if (!busy) setOpen(false); }} onSubmit={async reason => {
        if (busy) return;
        setBusy(true); setError(null);
        try { await onDelete(reason); setOpen(false); await onDeleted(); }
        catch (caught) { setError(caught instanceof ApiError ? caught.message : "Could not delete the record."); }
        finally { setBusy(false); }
      }} /> : null}
  </>;
}
