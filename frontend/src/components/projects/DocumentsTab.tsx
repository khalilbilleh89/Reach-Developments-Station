"use client";

import * as ui from "@/components/ui";
import { useCallback, useEffect, useState } from "react";
import { DraftBoundary } from "@/components/ui/UnsavedChangesGuard";
import { ApiError, projects } from "@/lib/api";
import type { DocumentReference, LandParcel, Permit } from "@/lib/api";
import { sectionDescription } from "@/components/shell/navigation";
import { Button, Card, DataToolbar, DensitySwitch, EmptyState, ExternalLink, Field, FieldRow, FilterChips, FormActions, IdentityCell, Loading, Notice, PageHeader, RecordPage, RowMenu, SavedViews, Segmented, SortHeader, StatusDot, TableScroll, ToolbarFilter, useSort } from "@/components/ui";
import { EditForm, asValue } from "@/components/projects/EditForm";
import type { EditField } from "@/components/projects/EditForm";
import { DeleteRecordButton } from "@/components/projects/DeleteRecordButton";

type DocumentType = { id: string; code: string; label: string; is_active: boolean; removable: boolean };
const blank = { title: "", document_type_code: "", external_url: "", reference_number: "", attach_to: "" };
const NO_DOCUMENTS: DocumentReference[] = [];
type Supports = "" | "project" | "parcel" | "permit";
type Standing = "" | "current" | "superseded";
const SUPPORTS: { value: Supports; label: string }[] = [{ value: "", label: "Anything" }, { value: "project", label: "Project" }, { value: "parcel", label: "Parcels" }, { value: "permit", label: "Permits" }];
const STANDING: { value: Standing; label: string }[] = [{ value: "", label: "Any state" }, { value: "current", label: "Current" }, { value: "superseded", label: "Superseded" }];
const message = (caught: unknown) => caught instanceof ApiError || caught instanceof Error ? caught.message : "Could not save the document.";

export function DocumentsTab({ projectId, canWrite }: { projectId: string; canWrite: boolean }) {
  const [rows, setRows] = useState<DocumentReference[] | null>(null);
  const [types, setTypes] = useState<DocumentType[]>([]);
  const [parcels, setParcels] = useState<LandParcel[]>([]);
  const [permits, setPermits] = useState<Permit[]>([]);
  const [form, setForm] = useState(blank);
  const [file, setFile] = useState<File | null>(null);
  const [mode, setMode] = useState("link");
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<DocumentReference | null>(null);
  const [typeName, setTypeName] = useState("");
  const [managingTypes, setManagingTypes] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [readError, setReadError] = useState<string | null>(null);
  const [lookupError, setLookupError] = useState<string | null>(null);
  // The barrel's hook, or a no-op where a test harness stands the barrel in.
  const { toast } = typeof ui.useToast === "function" ? ui.useToast() : { toast: () => {} };
  const setNotice = (text: string | null) => { if (text) toast({ title: text }); };
  const [busy, setBusy] = useState(false);
  // The register's own narrowing: every row is already on screen, so these
  // only choose which of them to show.
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [supports, setSupports] = useState<Supports>("");
  const [standing, setStanding] = useState<Standing>("");

  const load = useCallback(async () => {
    try { setRows(await projects.documents(projectId)); setReadError(null); }
    catch (caught) { setReadError(message(caught)); }
  }, [projectId]);
  const loadChoices = useCallback(async () => {
    const [typeResult, parcelResult, permitResult] = await Promise.allSettled([
      projects.documentTypes(projectId), projects.parcels(projectId), projects.permits(projectId),
    ]);
    if (typeResult.status === "fulfilled") setTypes(typeResult.value);
    if (parcelResult.status === "fulfilled") setParcels(parcelResult.value);
    if (permitResult.status === "fulfilled") setPermits(permitResult.value.permits ?? []);
    const failed = [typeResult, parcelResult, permitResult].find(result => result.status === "rejected");
    setLookupError(failed?.status === "rejected" ? message(failed.reason) : null);
  }, [projectId]);
  useEffect(() => { void (async () => { await Promise.all([load(), loadChoices()]); })(); }, [load, loadChoices]);

  const reset = () => { setForm(blank); setFile(null); setMode("link"); setError(null); setTypeName(""); };
  const submit = async (event: React.FormEvent) => {
    event.preventDefault(); setBusy(true); setError(null);
    try {
      const payload: Record<string, string> = { title: form.title, document_type_code: form.document_type_code };
      if (form.reference_number) payload.reference_number = form.reference_number;
      if (form.attach_to.startsWith("parcel:")) payload.parcel_id = form.attach_to.slice(7);
      if (form.attach_to.startsWith("permit:")) payload.permit_id = form.attach_to.slice(7);
      if (mode === "pdf") {
        if (!file) throw new Error("Choose a PDF file.");
        await projects.uploadDocument(projectId, payload, file);
      } else { await projects.createDocument(projectId, { ...payload, external_url: form.external_url }); }
      reset(); setCreating(false); setNotice("Document recorded."); await load();
    } catch (caught) { setError(message(caught)); } finally { setBusy(false); }
  };
  const addType = async (event: React.FormEvent) => {
    event.preventDefault(); setBusy(true); setError(null);
    try {
      const saved = await projects.createDocumentType(projectId, typeName.trim());
      await loadChoices(); setForm(v => ({ ...v, document_type_code: saved.code })); setTypeName(""); setNotice("Document type added.");
    } catch (caught) { setError(message(caught)); } finally { setBusy(false); }
  };
  const typeLabel = useCallback((code: string) => types.find(v => v.code === code)?.label ?? code, [types]);
  const attachment = useCallback((row: DocumentReference) => row.parcel_id ? `Plot ${parcels.find(v => v.id === row.parcel_id)?.plot_number ?? "—"}` : row.permit_id ? permits.find(v => v.id === row.permit_id)?.permit_code ?? "Permit" : "Project", [parcels, permits]);
  // Ordering the register already on screen by the text each column shows.
  const readDocumentColumn = useCallback((row: DocumentReference, column: string): string | null => {
    switch (column) {
      case "document": return row.title;
      case "type": return typeLabel(row.document_type_code);
      case "reference": return row.reference_number;
      case "supports": return attachment(row);
      case "state": return row.is_active ? "Current" : "Superseded";
      default: return null;
    }
  }, [typeLabel, attachment]);
  const needle = search.trim().toLowerCase();
  const shown = (rows ?? NO_DOCUMENTS).filter(row =>
    (!typeFilter || row.document_type_code === typeFilter) &&
    (!supports || (supports === "parcel" ? !!row.parcel_id : supports === "permit" ? !!row.permit_id : !row.parcel_id && !row.permit_id)) &&
    (!standing || (standing === "current") === row.is_active) &&
    (!needle || [row.title, row.reference_number, row.filename, row.notes, typeLabel(row.document_type_code), attachment(row)].some(value => value?.toLowerCase().includes(needle))));
  const { sort, setSort, toggle, sorted } = useSort(shown, readDocumentColumn);
  const narrowed = !!(search || typeFilter || supports || standing);
  const clearFilters = () => { setSearch(""); setTypeFilter(""); setSupports(""); setStanding(""); };
  const chips = [
    typeFilter ? { key: "type", label: `Type: ${typeLabel(typeFilter)}`, onRemove: () => setTypeFilter("") } : null,
    supports ? { key: "supports", label: `Supports: ${SUPPORTS.find(option => option.value === supports)?.label}`, onRemove: () => setSupports("") } : null,
    standing ? { key: "state", label: STANDING.find(option => option.value === standing)?.label ?? standing, onRemove: () => setStanding("") } : null,
    search ? { key: "search", label: `“${search}”`, onRemove: () => setSearch("") } : null,
  ].filter((chip): chip is NonNullable<typeof chip> => chip !== null);
  const fields: EditField[] = [
    { name: "title", label: "Title" },
    { name: "document_type_code", label: "Document type", kind: "select", options: types.filter(v => v.is_active || v.code === editing?.document_type_code).map(v => ({ value: v.code, label: v.label })) },
    { name: "reference_number", label: "Reference number" },
    ...(!editing?.filename ? [{ name: "external_url", label: "Link" }] : []),
    { name: "notes", label: "Notes", kind: "textarea" },
  ];
  const alerts = <>{error ? <Notice tone="error">{error}</Notice> : null}{lookupError ? <><Notice tone="error">{lookupError}</Notice><Button onClick={() => void loadChoices()}>Retry document choices</Button></> : null}</>;
  const typeManager = <Card title="Document types" description="Types added here belong to this project. A type used in document history is protected from deletion.">
    <DraftBoundary dirty={!!typeName} busy={busy} onDiscard={() => setTypeName("")}><form onSubmit={addType}><Field label="New document type"><input className="input" required maxLength={200} disabled={busy} value={typeName} onChange={e => setTypeName(e.target.value)} /></Field><FormActions><Button type="submit" disabled={busy || !typeName.trim()}>Add type</Button></FormActions></form></DraftBoundary>
    {types.filter(v => v.removable).map(v => <div className="row-actions" key={v.id}><span>{v.label}</span><DeleteRecordButton label="type" recordName={v.label} onDelete={reason => projects.deleteDocumentType(projectId, v.id, reason)} onDeleted={async () => { if (form.document_type_code === v.code) setForm(f => ({ ...f, document_type_code: "" })); await loadChoices(); }} /></div>)}
  </Card>;

  return <>
    <PageHeader icon="documents" title="Documents" subtitle={sectionDescription("documents")} compact actions={canWrite ? <div className="row-actions"><Button onClick={() => { setError(null); setManagingTypes(true); }}>Document types</Button><Button variant="primary" onClick={() => { reset(); setCreating(true); }}>New document</Button></div> : undefined} />
    <div className="stack">{!creating && !editing && !managingTypes ? alerts : null}
      {rows && rows.length > 0 ? <>
        <DataToolbar framed search={{ value: search, onChange: setSearch, placeholder: "Title, reference, file or notes", label: "Search documents" }}
          count={{ shown: shown.length, total: rows.length, noun: "document" }} onReset={narrowed ? clearFilters : undefined} actions={<DensitySwitch />}>
          <ToolbarFilter label="Type" active={typeFilter !== ""}><select className="input" value={typeFilter} onChange={e => setTypeFilter(e.target.value)}><option value="">Any type</option>{types.map(v => <option key={v.id} value={v.code}>{v.label}</option>)}</select></ToolbarFilter>
          <ToolbarFilter label="Supports" active={supports !== ""}><Segmented<Supports> label="Supports" value={supports} onChange={setSupports} options={SUPPORTS} /></ToolbarFilter>
          <ToolbarFilter label="State" active={standing !== ""}><Segmented<Standing> label="State" value={standing} onChange={setStanding} options={STANDING} /></ToolbarFilter>
        </DataToolbar>
        <FilterChips chips={chips} onClearAll={clearFilters} />
        <SavedViews screen="project-documents" filters={{ search, type: typeFilter, supports, state: standing }} sort={sort} onApply={(saved, savedSort) => {
          setSearch(String(saved.search ?? "")); setTypeFilter(String(saved.type ?? ""));
          setSupports(SUPPORTS.find(option => option.value === saved.supports)?.value ?? "");
          setStanding(STANDING.find(option => option.value === saved.state)?.value ?? "");
          setSort(savedSort);
        }} />
      </> : null}
      {readError ? <><Notice tone="error">{readError}</Notice><Button onClick={() => { void load(); void loadChoices(); }}>Retry documents</Button></> : rows === null ? <Loading label="Loading documents…" shape="rows" rows={4} /> : <Card flush>{rows.length === 0 ? <EmptyState title="No documents" hint="Add a link or upload a PDF supporting this project's records." /> : shown.length === 0 ? <EmptyState title="No document matches" hint="Widen the search or clear the filters to see the rest of the register." actions={<Button onClick={clearFilters}>Clear filters</Button>} /> : <TableScroll fixedFirst stickyHeader label="Document references"><thead><tr><SortHeader column="document" sort={sort} onToggle={toggle}>Document</SortHeader><SortHeader column="type" sort={sort} onToggle={toggle}>Type</SortHeader><SortHeader column="reference" sort={sort} onToggle={toggle}>Reference</SortHeader><SortHeader column="supports" sort={sort} onToggle={toggle}>Supports</SortHeader><SortHeader column="state" sort={sort} onToggle={toggle}>State</SortHeader><th scope="col">Open</th>{canWrite ? <th scope="col">Actions</th> : null}</tr></thead><tbody>{sorted.map(row => <tr key={row.id}><th scope="row"><IdentityCell name={row.title} meta={row.filename ?? row.notes ?? undefined} /></th><td>{typeLabel(row.document_type_code)}</td><td>{row.reference_number ?? "—"}</td><td>{attachment(row)}</td><td><StatusDot tone={row.is_active ? "success" : "muted"}>{row.is_active ? "Current" : "Superseded"}</StatusDot></td><td>{row.filename ? <Button small onClick={() => { void projects.downloadDocument(projectId, row).catch(caught => setError(message(caught))); }}>Download PDF</Button> : row.external_url ? <ExternalLink href={row.external_url}>Open</ExternalLink> : "—"}</td>{canWrite ? <td className="row-menu-cell"><RowMenu label={`Actions for ${row.title}`}><Button onClick={() => { setError(null); setEditing(row); }}>Edit</Button><Button onClick={() => { void projects.updateDocument(projectId, row.id, { is_active: !row.is_active }).then(load).catch(caught => setError(message(caught))); }}>{row.is_active ? "Supersede" : "Restore"}</Button><DeleteRecordButton label="document" recordName={row.title} confirmLabel="Delete document" description="Remove this document from the register. Its evidence and audit history are retained." onDelete={reason => projects.deleteDocument(projectId, row.id, reason)} onDeleted={load} /></RowMenu></td> : null}</tr>)}</tbody></TableScroll>}</Card>}
    </div>
    {creating ? <RecordPage icon="documents" title="New document" onClose={() => { setCreating(false); reset(); }}><div className="stack">{alerts}
      <Card title="Document details" description="Add an external link or upload a PDF up to 10 MB."><DraftBoundary dirty={JSON.stringify(form) !== JSON.stringify(blank) || !!file} busy={busy} onDiscard={reset}><form onSubmit={submit}><FieldRow columns={3}>
        <Field label="Title"><input className="input" required maxLength={200} disabled={busy} value={form.title} onChange={e => setForm({ ...form, title: e.target.value })} /></Field>
        <Field label="Document type" hint={types.some(v => v.is_active) ? undefined : "Add a document type below to get started."}><select className="input" required disabled={busy} value={form.document_type_code} onChange={e => setForm({ ...form, document_type_code: e.target.value })}><option value="">Choose…</option>{types.filter(v => v.is_active).map(v => <option key={v.id} value={v.code}>{v.label}</option>)}</select></Field>
        <Field label="Reference number" optional><input className="input" maxLength={120} disabled={busy} value={form.reference_number} onChange={e => setForm({ ...form, reference_number: e.target.value })} /></Field>
        <Field label="Document source"><select className="input" disabled={busy} value={mode} onChange={e => setMode(e.target.value)}><option value="link">External link</option><option value="pdf">Upload PDF</option></select></Field>
        {mode === "link" ? <Field label="Link"><input className="input" required type="url" maxLength={2000} disabled={busy} value={form.external_url} onChange={e => setForm({ ...form, external_url: e.target.value })} /></Field> : <Field label="PDF file" hint="PDF only, up to 10 MB. The saved file is retained unchanged."><input className="input" type="file" accept=".pdf,application/pdf" required disabled={busy} onChange={e => setFile(e.target.files?.[0] ?? null)} /></Field>}
        <Field label="Supports"><select className="input" disabled={busy} value={form.attach_to} onChange={e => setForm({ ...form, attach_to: e.target.value })}><option value="">The project</option>{parcels.map(v => <option key={v.id} value={`parcel:${v.id}`}>Plot {v.plot_number}</option>)}{permits.map(v => <option key={v.id} value={`permit:${v.id}`}>{v.permit_code}</option>)}</select></Field>
      </FieldRow><FormActions><Button type="submit" variant="primary" disabled={busy}>{busy ? "Saving…" : "Save document"}</Button></FormActions></form></DraftBoundary></Card>{typeManager}
    </div></RecordPage> : null}
    {managingTypes ? <RecordPage icon="documents" title="Document types" onClose={() => setManagingTypes(false)}><div className="stack">{alerts}{typeManager}</div></RecordPage> : null}
    {editing ? <RecordPage icon="documents" title="Edit document" subtitle={editing.title} onClose={() => setEditing(null)}><div className="stack">{alerts}<Card title="Document metadata"><EditForm fields={fields} initial={Object.fromEntries(fields.map(field => [field.name, asValue(editing[field.name as keyof DocumentReference] as never)]))} onSave={async changes => { await projects.updateDocument(projectId, editing.id, changes); await load(); setNotice("Document updated."); }} onCancel={() => setEditing(null)} /></Card></div></RecordPage> : null}
  </>;
}
