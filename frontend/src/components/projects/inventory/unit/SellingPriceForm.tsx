"use client";

import { useState } from "react";
import { ApiError, pricing } from "@/lib/api";
import { Button, Field, FieldRow, FormActions, FormSection, Notice } from "@/components/ui";

/** Direct entry creates a draft; approval and activation remain separate actions. */
export function SellingPriceForm({ projectId, unitId, currencyCode, onChanged }: {
  projectId: string;
  unitId: string;
  currencyCode: string | null;
  onChanged: () => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
  const [date, setDate] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) return <Button onClick={() => setOpen(true)}>Enter selling price</Button>;

  return (
    <form onSubmit={async event => {
      event.preventDefault();
      setBusy(true);
      setError(null);
      try {
        await pricing.createPriceVersion(projectId, unitId, {
          selling_price: amount,
          change_reason: reason,
          valid_from: date || null,
        });
        setOpen(false);
        setAmount("");
        setReason("");
        setDate("");
        await onChanged();
      } catch (caught) {
        setError(caught instanceof ApiError ? caught.message : "Could not save the selling price.");
      } finally {
        setBusy(false);
      }
    }}>
      <FormSection title="Enter selling price" description="Enter the total before tax in the project base currency. Save a draft, then submit it for approval by a different person. Approved measurements are required; pricing configuration is not.">
        {error ? <Notice tone="error">{error}</Notice> : null}
        <FieldRow columns={3}>
          <Field label={`Selling price (${currencyCode ?? "project base currency"}, ex tax)`}>
            <input className="input" required inputMode="decimal" disabled={busy} value={amount} onChange={e => setAmount(e.target.value)} />
          </Field>
          <Field label="Reason">
            <input className="input" required maxLength={500} disabled={busy} value={reason} onChange={e => setReason(e.target.value)} />
          </Field>
          <Field label="Effective date" hint="Leave blank for today.">
            <input className="input" type="date" disabled={busy} value={date} onChange={e => setDate(e.target.value)} />
          </Field>
        </FieldRow>
      </FormSection>
      <FormActions>
        <Button type="submit" disabled={busy}>Save price draft</Button>
        <Button disabled={busy} onClick={() => setOpen(false)}>Cancel</Button>
      </FormActions>
    </form>
  );
}
