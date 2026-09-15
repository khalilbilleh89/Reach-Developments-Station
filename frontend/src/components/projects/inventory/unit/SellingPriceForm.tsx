"use client";

import { useState } from "react";
import { ApiError, pricing } from "@/lib/api";
import { Button, Field, FieldRow, FormActions, FormSection, Notice } from "@/components/ui";

/** Direct entry creates a draft; approval and activation remain separate actions. */
export function SellingPriceForm({ projectId, unitId, currencyCode, currentAmount = null, isMasterAdmin = false, onChanged }: {
  projectId: string;
  unitId: string;
  currencyCode: string | null;
  currentAmount?: string | null;
  isMasterAdmin?: boolean;
  onChanged: () => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [amount, setAmount] = useState("");
  const [date, setDate] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) return <Button onClick={() => { setAmount(currentAmount ?? ""); setOpen(true); }}>{currentAmount !== null ? "Edit selling price" : "Enter selling price"}</Button>;

  return (
    <form onSubmit={async event => {
      event.preventDefault();
      setBusy(true);
      setError(null);
      try {
        await pricing.createPriceVersion(projectId, unitId, {
          selling_price: amount,
          valid_from: date || null,
        });
        setOpen(false);
        setAmount("");
        setDate("");
        await onChanged();
      } catch (caught) {
        setError(caught instanceof ApiError ? caught.message : "Could not save the selling price.");
      } finally {
        setBusy(false);
      }
    }}>
      <FormSection title={currentAmount !== null ? "Correct selling price" : "Enter selling price"} description={`Enter the total before tax in the project base currency. A correction creates a new version and preserves the previous price. Save, submit, approve, then activate the replacement. ${isMasterAdmin ? "As Master Administrator, you can approve your own correction with a recorded rationale." : "Approval requires a different person."}`}>
        {error ? <Notice tone="error">{error}</Notice> : null}
        <FieldRow columns={2}>
          <Field label={`Selling price (${currencyCode ?? "project base currency"}, ex tax)`}>
            <input className="input" required inputMode="decimal" disabled={busy} value={amount} onChange={e => setAmount(e.target.value)} />
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
