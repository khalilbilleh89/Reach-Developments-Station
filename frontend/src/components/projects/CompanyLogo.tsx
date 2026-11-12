"use client";
import { useState } from "react";
import { companyLogos, type Company } from "@/lib/api/companies";
import { Button, DraftBoundary, Field, FormActions, Icon, Notice, RecordPage } from "@/components/ui";
import { DeleteRecordButton } from "./DeleteRecordButton";

const nameOf = (company: Company) => company.legal_name || company.trading_name || "Company";

/** The company's mark in the identity tile: the stored logo, or the module glyph when none is stored. */
export function CompanyLogoTile({ projectId, company }: { projectId: string; company: Company }) {
  return <span className={company.logo_id ? "company-logo-tile company-logo-tile-image" : "company-logo-tile"}>
    {company.logo_id
      // Authenticated same-origin image; the server returns normalized PNG pixels.
      // eslint-disable-next-line @next/next/no-img-element
      ? <img src={companyLogos.url(projectId, company.id, company.logo_id)} alt={`${nameOf(company)} logo`} />
      : <Icon name="inventory" />}
  </span>;
}

/**
 * Logo actions for the company's menu: add one when none is stored, or remove
 * the current one. A replacement is uploaded after the current logo is removed.
 * The editor keeps its own state, so it survives the menu closing behind it.
 */
export function CompanyLogoActions({ projectId, company, onSaved }: { projectId: string; company: Company; onSaved: () => void }) {
  const [editing, setEditing] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return <>
    {company.logo_id
      ? <DeleteRecordButton label="logo" recordName={nameOf(company)} confirmLabel="Delete logo" description="Remove this logo from the company. The image and audit history are retained. Delete the current logo before uploading a replacement." onDelete={reason => companyLogos.remove(projectId, company.id, company.logo_id!, reason)} onDeleted={async () => onSaved()} />
      : <Button variant="quiet" onClick={() => { setFile(null); setError(null); setEditing(true); }}>Add logo</Button>}
    {editing ? <RecordPage icon="inventory" title="Add company logo" subtitle={nameOf(company)} onClose={() => setEditing(false)}><DraftBoundary dirty={file !== null} busy={busy}>
      <form className="stack" onSubmit={async event => {
        event.preventDefault(); if (busy || !file) return; setBusy(true); setError(null);
        try { await companyLogos.create(projectId, company.id, file); setEditing(false); setFile(null); onSaved(); }
        catch (caught) { setError(caught instanceof Error ? caught.message : "Could not upload the logo. Your selection has been kept."); }
        finally { setBusy(false); }
      }}>
        {error ? <Notice tone="error">{error}</Notice> : null}
        <Field label="Company logo" hint="PNG, JPEG or WebP, up to 5 MB and 4 million pixels."><input className="input" type="file" accept="image/png,image/jpeg,image/webp" required disabled={busy} onChange={event => setFile(event.target.files?.[0] ?? null)} /></Field>
        <FormActions><Button type="submit" variant="primary" disabled={busy || !file}>{busy ? "Uploading…" : "Save logo"}</Button><Button disabled={busy} data-leaves-editor onClick={() => setEditing(false)}>Cancel</Button></FormActions>
      </form>
    </DraftBoundary></RecordPage> : null}
  </>;
}
