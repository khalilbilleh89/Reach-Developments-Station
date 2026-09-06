"use client";
import { useState } from "react";
import type { SaleContract } from "@/lib/api";
import { Button, Field, FieldRow, FormActions, SubPanel } from "@/components/ui";
import { todayISO } from "@/lib/format";

export function SpaDetailsForm({ sale, busy, onSave }: {
  sale: SaleContract; busy: boolean; onSave: (body: Record<string, unknown>) => Promise<void>;
}) {
  const [number, setNumber] = useState(sale.spa_number ?? "");
  const [date, setDate] = useState(sale.contract_date ?? todayISO());
  return <SubPanel title="SPA details"><form onSubmit={(event) => {
    event.preventDefault(); if (!busy) void onSave({ spa_number: number.trim() || null, contract_date: date });
  }}>
    <FieldRow columns={2}>
      <Field label="SPA number" optional><input className="input" maxLength={64} value={number} onChange={(e) => setNumber(e.target.value)} /></Field>
      <Field label="Contract date"><input className="input" type="date" required value={date} onChange={(e) => setDate(e.target.value)} /></Field>
    </FieldRow>
    <p className="footnote">Save these details before submitting for signature. Legal records the buyer and seller signing dates separately.</p>
    <FormActions><Button type="submit" disabled={busy}>Save SPA details</Button></FormActions>
  </form></SubPanel>;
}
