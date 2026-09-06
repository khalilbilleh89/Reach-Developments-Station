"use client";

import { useState } from "react";
import { ApiError, sales } from "@/lib/api";
import type { SalesClient } from "@/lib/api";
import { Button, Field, FieldRow, FormActions, Notice } from "@/components/ui";

export function BuyerForm({ projectId, onSaved, onCancel }: {
  projectId: string;
  onSaved: (buyer: SalesClient) => void;
  onCancel: () => void;
}) {
  const [form, setForm] = useState({ name: "", email: "", phone: "", sole: true });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return (
    <form onSubmit={async (event) => {
      event.preventDefault();
      if (busy) return;
      setBusy(true);
      setError(null);
      try {
        const buyer = await sales.createClient(projectId, {
          display_name: form.name.trim(),
          ...(form.sole ? { sole_purchaser_name: form.name.trim() } : {}),
          ...(form.email.trim() ? { email: form.email.trim() } : {}),
          ...(form.phone.trim() ? { phone: form.phone.trim() } : {}),
        });
        onSaved(buyer);
      } catch (caught) {
        setError(caught instanceof ApiError ? caught.message : "Could not add the buyer.");
      } finally { setBusy(false); }
    }}>
      {error ? <Notice tone="error">{error}</Notice> : null}
      <FieldRow columns={3}>
        <Field label="Buyer name" hint="For a sole purchaser, enter the full name as shown on their identification.">
          <input className="input" required maxLength={200} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        </Field>
        <Field label="Phone" optional><input className="input" type="tel" maxLength={64} value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} /></Field>
        <Field label="Email" optional><input className="input" type="email" maxLength={320} value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></Field>
      </FieldRow>
      <label className="checkbox"><input type="checkbox" checked={form.sole} onChange={(e) => setForm({ ...form, sole: e.target.checked })} /><span>This buyer is the sole purchaser (100% ownership).</span></label>
      {!form.sole ? <p className="footnote">Add the joint purchasers and their shares in Buyers before activating the reservation.</p> : null}
      <FormActions><Button type="submit" variant="primary" disabled={busy || !form.name.trim()}>Add buyer</Button><Button disabled={busy} onClick={onCancel}>Cancel</Button></FormActions>
    </form>
  );
}
