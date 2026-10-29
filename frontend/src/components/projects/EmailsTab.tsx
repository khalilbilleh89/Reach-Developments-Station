"use client";

import { useState } from "react";
import { ApiError } from "@/lib/api";
import { emails } from "@/lib/api/emails";
import type { Email, EmailCategory } from "@/lib/api/emails";
import { useAnswer } from "@/lib/answer";
import { SALES_READERS, hasAnyRole } from "@/lib/roles";
import { Button, Card, DataToolbar, DraftBoundary, EmptyState, Field, FormActions, Loading, Notice, PageHeader, RecordPage, Tabs, TabPanel } from "@/components/ui";
import { DeleteRecordButton } from "./DeleteRecordButton";

const categories: {key: EmailCategory; label: string}[] = [
  {key: "internal", label: "Internal Emails"},
  {key: "clients", label: "Clients Emails"},
  {key: "external", label: "External Emails"},
];

export function EmailsTab({projectId, roles}: {projectId: string; roles: Set<string>}) {
  const [category, setCategory] = useState<EmailCategory>("internal");
  const [search, setSearch] = useState("");
  const [editor, setEditor] = useState<Email | "new" | null>(null);
  const [composer, setComposer] = useState<Email | null>(null);
  const answer = useAnswer(hasAnyRole(roles, SALES_READERS), () => emails.list(projectId), [projectId]);
  const changed = async () => { setEditor(null); answer.retry(); };
  if (answer.status === "off") return null;
  if (answer.status === "loading") return <Loading label="Loading email templates" />;
  if (answer.status === "denied") return <Notice tone="info">Emails are not available to your role.</Notice>;
  if (answer.status === "failed") return <Notice tone="error">{answer.message} <Button onClick={answer.retry}>Retry</Button></Notice>;
  if (editor !== null) return <EmailEditor projectId={projectId} row={editor === "new" ? null : editor} category={category} onClose={() => setEditor(null)} onSaved={changed} />;
  if (composer) return <EmailComposer row={composer} onClose={() => setComposer(null)} />;
  const needle = search.trim().toLocaleLowerCase();
  const rows = answer.data.items.filter(row => row.category === category && `${row.title}\n${row.subject}\n${row.body}`.toLocaleLowerCase().includes(needle));
  return <div className="stack">
    <PageHeader title="Emails" subtitle="Save templates, customize a response, then copy it into your email app." compact actions={answer.data.can_edit ? <Button variant="primary" onClick={() => setEditor("new")}>Add template</Button> : undefined} />
    <Tabs label="Email categories" tabs={categories} active={category} onSelect={value => setCategory(value as EmailCategory)} />
    <TabPanel group="Email categories" tab={category}>
      <DataToolbar search={{value: search, onChange: setSearch, label: "Search email templates", placeholder: "Search title, subject or body…"}} onReset={search ? () => setSearch("") : undefined} />
      {rows.length ? rows.map(row => <Card key={`${row.id}:${row.version}`} title={row.title} actions={<Button onClick={() => setComposer(row)}>Customize &amp; copy</Button>}>
        <div className="stack">
          <p className="faq-answer" dir="auto"><strong>Subject: </strong>{row.subject}</p>
          <details><summary>Preview email</summary><p className="faq-answer" dir="auto">{row.body}</p></details>
          {answer.data.can_edit ? <FormActions>
            <Button onClick={() => setEditor(row)}>Edit template</Button>
            <DeleteRecordButton label="email template" recordName={row.title} description="This removes the saved template from this project's library. Its full audit history is retained." destructive onDelete={reason => emails.delete(projectId, row, reason)} onDeleted={changed} />
          </FormActions> : null}
        </div>
      </Card>) : <EmptyState title={needle ? "No matching templates" : "No templates in this section yet"} hint={needle ? "Try another word or clear your search." : "Create a reusable email or response for this category."} />}
    </TabPanel>
  </div>;
}

export function EmailEditor({projectId, row, category: initialCategory, onClose, onSaved}: {
  projectId: string; row: Email | null; category: EmailCategory; onClose: () => void; onSaved: () => Promise<void>;
}) {
  const [category, setCategory] = useState<EmailCategory>(row?.category ?? initialCategory);
  const [title, setTitle] = useState(row?.title ?? "");
  const [subject, setSubject] = useState(row?.subject ?? "");
  const [body, setBody] = useState(row?.body ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dirty = category !== (row?.category ?? initialCategory) || title !== (row?.title ?? "") || subject !== (row?.subject ?? "") || body !== (row?.body ?? "");
  return <RecordPage title={row ? "Edit email template" : "Add email template"} subtitle="Use placeholders such as [Client name] and replace them when preparing an email. Templates are shared with this project's Commercial readers." onClose={onClose}>
    <DraftBoundary dirty={dirty} busy={busy}>
      <form className="stack" onSubmit={async event => {
        event.preventDefault(); if (busy) return; setBusy(true); setError(null);
        try {
          const input = {category, title: title.trim(), subject: subject.trim(), body: body.trim()};
          if (row) await emails.update(projectId, row, input); else await emails.create(projectId, input);
          await onSaved();
        } catch (caught) { setError(caught instanceof ApiError ? caught.message : "Could not save the template. Your text is still here."); }
        finally { setBusy(false); }
      }}>
        {error ? <Notice tone="error">{error}</Notice> : null}
        <Field label="Category"><select className="input" disabled={busy} value={category} onChange={event => setCategory(event.target.value as EmailCategory)}>{categories.map(item => <option key={item.key} value={item.key}>{item.label}</option>)}</select></Field>
        <Field label="Template title"><input className="input" dir="auto" required maxLength={500} disabled={busy} value={title} onChange={event => setTitle(event.target.value)} /></Field>
        <Field label="Subject"><input className="input" dir="auto" required maxLength={500} disabled={busy} value={subject} onChange={event => setSubject(event.target.value)} /></Field>
        <Field label="Email body"><textarea className="input" dir="auto" required maxLength={20000} rows={14} disabled={busy} value={body} onChange={event => setBody(event.target.value)} /></Field>
        <FormActions>
          <Button type="submit" variant="primary" disabled={busy || !dirty || !title.trim() || !subject.trim() || !body.trim()}>{busy ? "Saving…" : "Save template"}</Button>
          <Button data-leaves-editor disabled={busy} onClick={onClose}>Cancel</Button>
        </FormActions>
      </form>
    </DraftBoundary>
  </RecordPage>;
}

export function EmailComposer({row, onClose}: {row: Email; onClose: () => void}) {
  const [subject, setSubject] = useState(row.subject);
  const [body, setBody] = useState(row.body);
  const [status, setStatus] = useState("");
  const copy = async (value: string, label: string) => {
    setStatus("");
    try { await navigator.clipboard.writeText(value); setStatus(`${label} copied.`); }
    catch { setStatus("Copy is unavailable. Select the text in the fields and copy it manually."); }
  };
  return <RecordPage title={row.title} subtitle="Customize this email for the recipient. Your saved template stays unchanged; this draft is kept only while this page is open." onClose={onClose}>
    <DraftBoundary dirty={subject !== row.subject || body !== row.body}>
      <div className="stack">
        <Field label="Subject"><input className="input" dir="auto" maxLength={500} value={subject} onChange={event => {setSubject(event.target.value); setStatus("");}} /></Field>
        <Field label="Email body"><textarea className="input" dir="auto" rows={16} maxLength={20000} value={body} onChange={event => {setBody(event.target.value); setStatus("");}} /></Field>
        <FormActions>
          <Button variant="primary" onClick={() => copy(body, "Email body")}>Copy body</Button>
          <Button onClick={() => copy(subject, "Subject")}>Copy subject</Button>
          <Button onClick={() => copy(`Subject: ${subject}\n\n${body}`, "Email")}>Copy entire email</Button>
        </FormActions>
        <p role="status">{status}</p>
      </div>
    </DraftBoundary>
  </RecordPage>;
}
