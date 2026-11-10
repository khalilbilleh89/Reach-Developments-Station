"use client";
import { useState } from "react";
import { companyLogos, type Company } from "@/lib/api/companies";
import { Button, DraftBoundary, Field, FormActions, Notice, RecordPage } from "@/components/ui";
import { DeleteRecordButton } from "./DeleteRecordButton";

export function CompanyLogo({ projectId, company, canWrite, onSaved }: { projectId: string; company: Company; canWrite: boolean; onSaved: () => void }) {
  const [editing, setEditing] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return <div className="stack">
    {company.logo_id ? <div className="stack">
      {/* Authenticated same-origin image; the server returns normalized PNG pixels. */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={companyLogos.url(projectId, company.id, company.logo_id)} alt={`${company.legal_name || company.trading_name || "Company"} logo`} width={160} height={100} style={{ objectFit: "contain", objectPosition: "left" }} />
      {canWrite ? <DeleteRecordButton label="company logo" recordName={company.legal_name || "Company logo"} confirmLabel="Delete logo" description="Remove this logo from the company. The image and audit history are retained. Delete the current logo before uploading a replacement." onDelete={reason => companyLogos.remove(projectId, company.id, company.logo_id!, reason)} onDeleted={async () => onSaved()} /> : null}
    </div> : canWrite ? <Button variant="default" onClick={() => { setFile(null); setError(null); setEditing(true); }}>Add company logo</Button> : null}
    {editing ? <RecordPage title="Add company logo" onClose={() => setEditing(false)}><DraftBoundary dirty={file !== null} busy={busy}>
      <form className="stack" onSubmit={async event => {
        event.preventDefault(); if (busy || !file) return; setBusy(true); setError(null);
        try { await companyLogos.create(projectId, company.id, file); setEditing(false); setFile(null); onSaved(); }
        catch (caught) { setError(caught instanceof Error ? caught.message : "Could not upload the logo. Your selection has been kept."); }
        finally { setBusy(false); }
      }}>
        {error ? <Notice tone="error">{error}</Notice> : null}
        <Field label="Company logo" hint="PNG, JPEG or WebP, up to 5 MB and 4 million pixels."><input className="input" type="file" accept="image/png,image/jpeg,image/webp" required disabled={busy} onChange={event => setFile(event.target.files?.[0] ?? null)} /></Field>
        <FormActions><Button type="submit" disabled={busy || !file}>{busy ? "Uploading…" : "Save logo"}</Button><Button variant="default" disabled={busy} data-leaves-editor onClick={() => setEditing(false)}>Cancel</Button></FormActions>
      </form>
    </DraftBoundary></RecordPage> : null}
  </div>;
}
