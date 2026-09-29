"use client";

import { useState } from "react";
import { ApiError } from "@/lib/api";
import { faqs } from "@/lib/api/faqs";
import type { Faq } from "@/lib/api/faqs";
import { useAnswer } from "@/lib/answer";
import { SALES_READERS, hasAnyRole } from "@/lib/roles";
import { Button, Card, DataToolbar, DraftBoundary, EmptyState, Field, FormActions, Loading, Notice, PageHeader, RecordPage } from "@/components/ui";
import { DeleteRecordButton } from "./DeleteRecordButton";

export function FaqTab({projectId, roles}: {projectId: string; roles: Set<string>}) {
  const [search, setSearch] = useState("");
  const [editor, setEditor] = useState<Faq | "new" | null>(null);
  const answer = useAnswer(hasAnyRole(roles, SALES_READERS), () => faqs.list(projectId), [projectId]);
  const changed = async () => { setEditor(null); answer.retry(); };
  if (answer.status === "off") return null;
  if (answer.status === "loading") return <Loading label="Loading FAQs" />;
  if (answer.status === "denied") return <Notice tone="info">FAQs are not available to your role.</Notice>;
  if (answer.status === "failed") return <Notice tone="error">{answer.message} <Button onClick={answer.retry}>Retry</Button></Notice>;
  if (editor !== null) return <FaqEditor projectId={projectId} row={editor === "new" ? null : editor} onClose={() => setEditor(null)} onSaved={changed} />;
  const needle = search.trim().toLocaleLowerCase();
  const rows = answer.data.items.filter(row => `${row.question}\n${row.answer}`.toLocaleLowerCase().includes(needle));
  return <div className="stack">
    <PageHeader title="FAQs" subtitle="Save clear answers to common questions, ready to copy and share." compact actions={answer.data.can_edit ? <Button variant="primary" onClick={() => setEditor("new")}>Add FAQ</Button> : undefined} />
    <DataToolbar search={{value: search, onChange: setSearch, label: "Search questions and answers", placeholder: "Search questions and answers…"}} onReset={search ? () => setSearch("") : undefined} />
    {rows.length ? rows.map(row => <FaqCard key={`${row.id}:${row.version}`} row={row} projectId={projectId} canEdit={answer.data.can_edit} onEdit={() => setEditor(row)} onChanged={changed} />) : <EmptyState title={needle ? "No matching FAQs" : "No FAQs yet"} hint={needle ? "Try another word or clear your search." : "Add your first question and answer to build this project's FAQ library."} />}
  </div>;
}

export function FaqCard({row, projectId, canEdit, onEdit, onChanged}: {
  row: Faq; projectId: string; canEdit: boolean; onEdit: () => void; onChanged: () => Promise<void>;
}) {
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState(false);
  return <Card title={row.question} actions={<Button onClick={async () => {
    setCopied(false); setCopyError(false);
    try { await navigator.clipboard.writeText(row.answer); setCopied(true); }
    catch { setCopyError(true); }
  }}>Copy answer</Button>}>
    <div className="stack">
      <p className="faq-answer" dir="auto">{row.answer}</p>
      <span role="status">{copied ? "Answer copied." : ""}</span>
      {copyError ? <Notice tone="info">Copy is unavailable in this browser. Select the answer above and copy it manually.</Notice> : null}
      {canEdit ? <FormActions>
        <Button onClick={onEdit}>Edit</Button>
        <DeleteRecordButton label="FAQ" recordName={row.question} description="This removes the question and answer from the FAQ library. Its audit history is retained." destructive onDelete={reason => faqs.delete(projectId, row, reason)} onDeleted={onChanged} />
      </FormActions> : null}
    </div>
  </Card>;
}

export function FaqEditor({projectId, row, onClose, onSaved}: {
  projectId: string; row: Faq | null; onClose: () => void; onSaved: () => Promise<void>;
}) {
  const [question, setQuestion] = useState(row?.question ?? "");
  const [answer, setAnswer] = useState(row?.answer ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dirty = question !== (row?.question ?? "") || answer !== (row?.answer ?? "");
  return <RecordPage title={row ? "Edit FAQ" : "Add FAQ"} subtitle="Write the answer exactly as you want to share it." onClose={onClose}>
    <DraftBoundary dirty={dirty} busy={busy}>
      <form className="stack" onSubmit={async event => {
        event.preventDefault(); if (busy) return; setBusy(true); setError(null);
        try {
          const input = {question: question.trim(), answer: answer.trim()};
          if (row) await faqs.update(projectId, row, input); else await faqs.create(projectId, input);
          await onSaved();
        } catch (caught) { setError(caught instanceof ApiError ? caught.message : "Could not save the FAQ. Your text is still here."); }
        finally { setBusy(false); }
      }}>
        {error ? <Notice tone="error">{error}</Notice> : null}
        <Field label="Question"><textarea className="input" dir="auto" required maxLength={500} rows={2} disabled={busy} value={question} onChange={event => setQuestion(event.target.value)} /></Field>
        <Field label="Answer"><textarea className="input" dir="auto" required maxLength={20000} rows={12} disabled={busy} value={answer} onChange={event => setAnswer(event.target.value)} /></Field>
        <FormActions>
          <Button type="submit" variant="primary" disabled={busy || !dirty || !question.trim() || !answer.trim()}>{busy ? "Saving…" : "Save FAQ"}</Button>
          <Button data-leaves-editor disabled={busy} onClick={onClose}>Cancel</Button>
        </FormActions>
      </form>
    </DraftBoundary>
  </RecordPage>;
}
