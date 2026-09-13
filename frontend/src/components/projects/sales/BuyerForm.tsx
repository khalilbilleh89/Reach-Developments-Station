"use client";
import { ValidationSummary } from "@/components/ui/ValidationSummary";

import { AgentFields, emptyAgent, agentPayload } from "./AgentFields";
import { useState } from "react";
import { ApiError, sales } from "@/lib/api";
import type { SalesClient } from "@/lib/api";
import { DraftBoundary, Button, Field, FieldRow, FormActions } from "@/components/ui";

export function BuyerForm({ projectId, onSaved, onCancel }: {
  projectId: string;
  onSaved: (buyer: SalesClient) => void;
  onCancel: () => void;
}) {
  const [agent, setAgent] = useState(emptyAgent);
  const [form, setForm] = useState({ name: "", email: "", phone: "", sole: true });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | ApiError | null>(null);
  return (
    <DraftBoundary dirty={Boolean(Object.values(agent).some(Boolean) || form.name || form.email || form.phone || !form.sole)} busy={busy}><form onSubmit={async (event) => {
      event.preventDefault();
      if (busy) return;
      setBusy(true);
      setError(null);
      try {
        const buyer = await sales.createClient(projectId, {
          ...agentPayload(agent),
          display_name: form.name.trim(),
          ...(form.sole ? { sole_purchaser_name: form.name.trim() } : {}),
          ...(form.email.trim() ? { email: form.email.trim() } : {}),
          ...(form.phone.trim() ? { phone: form.phone.trim() } : {}),
        });
        onSaved(buyer);
      } catch (caught) {
        setError(caught instanceof ApiError ? caught : "Could not add the buyer.");
      } finally { setBusy(false); }
    }}>
      <ValidationSummary error={error} />
      <FieldRow columns={3}>
        <Field label="Buyer name" hint="For a sole purchaser, enter the full name as shown on their identification.">
          <input className="input" required maxLength={200} name="display_name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        </Field>
        <Field label="Phone" optional><input className="input" type="tel" maxLength={64} name="phone" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} /></Field>
        <Field label="Email" optional><input className="input" type="email" maxLength={320} name="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></Field>
      </FieldRow>
      <AgentFields value={agent} onChange={setAgent} />
      <label className="checkbox"><input type="checkbox" checked={form.sole} onChange={(e) => setForm({ ...form, sole: e.target.checked })} /><span>This buyer is the sole purchaser (100% ownership).</span></label>
      {!form.sole ? <p className="footnote">Add the joint purchasers and their shares in Buyers before activating the reservation.</p> : null}
      <FormActions><Button type="submit" variant="primary" disabled={busy || !form.name.trim()}>Add buyer</Button><Button disabled={busy} data-leaves-editor onClick={onCancel}>Cancel</Button></FormActions>
    </form></DraftBoundary>
  );
}
