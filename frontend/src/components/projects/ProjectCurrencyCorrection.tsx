"use client";

import { useEffect, useState } from "react";

import { ApiError, projects, settings } from "@/lib/api";
import type { Currency, ProjectDetail } from "@/lib/api";
import {
  Button,
  Card,
  DraftBoundary,
  Field,
  Form,
  FormActions,
  Loading,
  Notice,
  RecordPage,
} from "@/components/ui";

export function ProjectCurrencyCorrection({
  project,
  onSaved,
  onClose,
}: {
  project: ProjectDetail;
  onSaved: () => Promise<void>;
  onClose: () => void;
}) {
  const [currencies, setCurrencies] = useState<Currency[] | null>(null);
  const [loadAttempt, setLoadAttempt] = useState(0);
  const [target, setTarget] = useState("");
  const [reason, setReason] = useState("");
  const [acknowledged, setAcknowledged] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    settings.currencies().then(rows => {
      if (active) {
        setCurrencies(rows);
        setError(null);
      }
    }).catch(caught => {
      if (active) {
        setError(caught instanceof ApiError ? caught.message : "Could not load currency options.");
      }
    });
    return () => { active = false; };
  }, [loadAttempt]);

  const available = (currencies ?? []).filter(
    currency => currency.is_active && currency.id !== project.base_currency_id,
  );
  const selected = available.find(currency => currency.id === target);
  const ready = Boolean(target && reason.trim().length >= 8 && acknowledged);

  async function submit(): Promise<void> {
    if (!ready || busy) return;
    setBusy(true);
    setError(null);
    try {
      await projects.correctCurrency(project.id, {
        expected_base_currency_id: project.base_currency_id,
        target_currency_id: target,
        reason,
        keep_amounts_unchanged: true,
      });
      await onSaved();
      onClose();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "The currency correction could not be completed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <RecordPage
      eyebrow="System administration"
      icon="money"
      title="Correct base currency"
      subtitle={project.name}
      onClose={onClose}
    >
      <Notice tone="warning">
        This does not convert values. Every numeric amount remains unchanged. Only the project
        denomination and eligible labels inherited from its mistaken base currency are corrected.
      </Notice>
      <Card>
        {currencies === null ? error ? (
          <div className="stack">
            <Notice tone="error">{error}</Notice>
            <Button onClick={() => { setError(null); setLoadAttempt(value => value + 1); }}>
              Try again
            </Button>
          </div>
        ) : <Loading label="Loading currencies…" /> : (
        <DraftBoundary
          dirty={Boolean(target || reason || acknowledged)}
          busy={busy}
          onDiscard={() => { setTarget(""); setReason(""); setAcknowledged(false); }}
        >
        <Form onSubmit={event => { event.preventDefault(); void submit(); }}>
          <div className="stack">
            <Field label="Current base currency">
              <input className="input" value={project.base_currency_code ?? project.base_currency_id} disabled />
            </Field>
            <Field label="New base currency" hint="Only active currencies are available.">
              <select className="input" required value={target} onChange={event => setTarget(event.target.value)}>
                <option value="">Choose currency</option>
                {available.map(currency => (
                  <option key={currency.id} value={currency.id}>{currency.code} — {currency.name}</option>
                ))}
              </select>
            </Field>
            <Field label="Reason" hint="At least eight characters. This is retained in audit history.">
              <textarea className="input" required minLength={8} maxLength={500} value={reason} onChange={event => setReason(event.target.value)} />
            </Field>
            <label className="checkbox">
              <input type="checkbox" checked={acknowledged} onChange={event => setAcknowledged(event.target.checked)} />
              <span>
                I understand that {project.base_currency_code ?? "the current currency"} becomes {selected?.code ?? "the selected currency"} while all recorded numbers stay exactly the same.
              </span>
            </label>
            {error ? <Notice tone="error">{error}</Notice> : null}
            <FormActions>
              <Button data-leaves-editor disabled={busy} onClick={onClose}>Cancel</Button>
              <Button type="submit" variant="danger" disabled={!ready || busy}>
                {busy ? "Correcting…" : "Correct denomination"}
              </Button>
            </FormActions>
          </div>
        </Form>
        </DraftBoundary>
        )}
      </Card>
    </RecordPage>
  );
}
