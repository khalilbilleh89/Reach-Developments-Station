"use client";
import { useState } from "react";
import { ApiError } from "@/lib/api";
import { escalations, type EscalationEntry } from "@/lib/api/escalations";
import { useAnswer } from "@/lib/answer";
import { Button, Card, DraftBoundary, EmptyState, Field, FieldRow, FormActions, FormSection, Loading, Notice, PageHeader, RecordPage, ValidationSummary } from "@/components/ui";
import { DeleteRecordButton } from "./DeleteRecordButton";

export function PriceEscalationTab({ projectId }: { projectId: string }) {
  const answer = useAnswer(true, () => escalations.list(projectId), [projectId]);
  const [editor, setEditor] = useState<{ entry?: EscalationEntry } | null>(null);
  const [notice, setNotice] = useState("");
  const rows = answer.status === "ready" ? answer.data.entries : [];
  const suggestions = [...new Set(["Pre-launch", "Launch", "Construction", "Foundation", ...rows.map(row => row.project_status)])];
  const canManage = answer.status === "ready" && answer.data.can_manage;
  return <div className="stack">
    <PageHeader title="Price Escalation" icon="money" subtitle="Record each price escalation, its effective date and the project stage at that time."
      actions={canManage ? <Button onClick={() => setEditor({})}>Add price escalation</Button> : undefined} />
    <Notice tone="info">These entries track your pricing strategy. Unit prices are maintained separately in Inventory.</Notice>
    {notice ? <div role="status"><Notice tone="success">{notice}</Notice></div> : null}
    {answer.status === "loading" ? <Loading label="Loading price escalations…" /> : null}
    {answer.status === "denied" || answer.status === "off" ? <Notice tone="info">Price escalation strategy is unavailable to your access level.</Notice> : null}
    {answer.status === "failed" ? <Notice tone="error">{answer.message} <Button variant="default" onClick={answer.retry}>Retry</Button></Notice> : null}
    {answer.status === "ready" ? <>
      <div className="form-actions"><span>{rows.length} price escalation entries · latest effective date first</span><Button variant="quiet" onClick={answer.retry}>Refresh</Button></div>
      {rows.length === 0 ? <Card><EmptyState title="No price escalations yet" hint="Add an effective date, percentage and project status to start your strategy history." /></Card> : null}
      {rows.map(row => <Card key={row.id}><div className="stack">
        <dl className="workspace-facts">
          <div><dt>Effective date</dt><dd>{row.effective_date}</dd></div>
          <div><dt>Price escalation %</dt><dd>{row.escalation_percent}%</dd></div>
          <div><dt>Project status</dt><dd>{row.project_status}</dd></div>
        </dl>
        {canManage ? <div className="form-actions"><Button variant="default" onClick={() => setEditor({ entry: row })}>Edit price escalation</Button>
          <DeleteRecordButton label="price escalation" recordName={row.effective_date + " / " + row.project_status}
            description="Remove this entry from the register. Its values and audit history are retained. Unit prices are unchanged."
            confirmLabel="Delete entry" onDelete={reason => escalations.remove(projectId, row, reason)}
            onDeleted={async () => { setNotice("Price escalation deleted."); answer.retry(); }} />
        </div> : null}
      </div></Card>)}
    </> : null}
    {editor ? <EscalationForm key={editor.entry?.id ?? "new"} projectId={projectId} entry={editor.entry} suggestions={suggestions}
      onClose={() => setEditor(null)} onSaved={() => { setEditor(null); setNotice("Price escalation saved."); answer.retry(); }} /> : null}
  </div>;
}

export function EscalationForm({ projectId, entry, suggestions, onClose, onSaved }: {
  projectId: string; entry?: EscalationEntry; suggestions: string[]; onClose: () => void; onSaved: () => void;
}) {
  const [original] = useState(() => ({ effective_date: entry?.effective_date ?? "", escalation_percent: entry?.escalation_percent ?? "", project_status: entry?.project_status ?? "" }));
  const [values, setValues] = useState(original);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | string | null>(null);
  const change = (key: keyof typeof values, value: string) => setValues(previous => ({ ...previous, [key]: value }));
  return <RecordPage eyebrow="FINANCE" icon="money" title={entry ? "Edit price escalation" : "Add price escalation"} onClose={onClose}>
    <DraftBoundary dirty={JSON.stringify(original) !== JSON.stringify(values)} busy={busy}>
      <form className="stack" onSubmit={async event => {
        event.preventDefault(); if (busy) return;
        if (!values.project_status.trim()) { setError("Enter a project status."); return; }
        setBusy(true); setError(null);
        try {
          const body = { ...values, project_status: values.project_status.trim() };
          if (entry) await escalations.update(projectId, entry, body); else await escalations.create(projectId, body);
          onSaved();
        } catch (caught) { setError(caught instanceof ApiError ? caught : "Could not save. Your entries have been kept."); }
        finally { setBusy(false); }
      }}>
        <ValidationSummary error={error} />
        <fieldset disabled={busy} className="stack">
          <FormSection title="Escalation details" description="Enter the percentage increase and the project status when it takes effect.">
            <FieldRow>
              <Field label="Effective date"><input className="input" type="date" name="effective_date" required value={values.effective_date} onChange={event => change("effective_date", event.target.value)} /></Field>
              <Field label="Price escalation %"><input className="input" type="number" name="escalation_percent" required min="0.0001" max="99999.9999" step="0.0001" placeholder="e.g. 5" value={values.escalation_percent} onChange={event => change("escalation_percent", event.target.value)} /></Field>
            </FieldRow>
            <Field label="Project status" hint="Choose a suggestion or type any status of your own."><input className="input" name="project_status" required maxLength={200} list="price-escalation-statuses" value={values.project_status} onChange={event => change("project_status", event.target.value)} />
              <datalist id="price-escalation-statuses">{suggestions.map(status => <option key={status} value={status} />)}</datalist>
            </Field>
          </FormSection>
        </fieldset>
        <FormActions><Button type="submit" disabled={busy}>{busy ? "Saving…" : "Save price escalation"}</Button><Button variant="default" disabled={busy} data-leaves-editor onClick={onClose}>Cancel</Button></FormActions>
      </form>
    </DraftBoundary>
  </RecordPage>;
}
