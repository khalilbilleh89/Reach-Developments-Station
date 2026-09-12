"use client";

import { useState } from "react";
import { Button, Field, FieldRow, FormActions } from "@/components/ui";

/** A direct selling price has no configured lock period, so ask for the date. */
export function RequoteForm({ busy, onSubmit }: {
  busy: boolean;
  onSubmit: (reason: string, lockDate?: string) => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [lockDate, setLockDate] = useState("");

  if (!open) return <Button variant="primary" disabled={busy} onClick={() => setOpen(true)}>Re-quote</Button>;

  return (
    <form onSubmit={event => { event.preventDefault(); void onSubmit(reason, lockDate || undefined); }}>
      <p className="subtle">Refresh the list-price reference. An explicitly agreed sales price is retained; existing exception approval is withdrawn.</p>
      <FieldRow columns={2}>
        <Field label="Reason for re-quote">
          <input className="input" required maxLength={500} disabled={busy} value={reason} onChange={e => setReason(e.target.value)} />
        </Field>
        <Field label="New price lock until" hint="Required for directly entered prices. Leave blank to use a configured period.">
          <input className="input" type="date" disabled={busy} value={lockDate} onChange={e => setLockDate(e.target.value)} />
        </Field>
      </FieldRow>
      <FormActions>
        <Button type="submit" variant="primary" disabled={busy}>Confirm re-quote</Button>
        <Button disabled={busy} onClick={() => setOpen(false)}>Cancel</Button>
      </FormActions>
    </form>
  );
}
