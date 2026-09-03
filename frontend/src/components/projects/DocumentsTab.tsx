"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, projects, settings } from "@/lib/api";
import type { DocumentReference, LandParcel, Permit, ReferenceValue } from "@/lib/api";
import { sectionDescription } from "@/components/shell/navigation";
import {
  Button,
  Card,
  EmptyState,
  Field,
  FieldRow,
  FormActions,
  Icon,
  Loading,
  Notice,
  PageHeader,
  StatusDot,
  TableScroll,
} from "@/components/ui";
import { EditForm, asValue } from "@/components/projects/EditForm";
import type { EditField } from "@/components/projects/EditForm";

/**
 * The metadata a reference carries. What it is attached to is fixed at
 * creation: moving evidence between records is not a metadata edit.
 */
const DOCUMENT_FIELDS: EditField[] = [
  { name: "title", label: "Title" },
  { name: "document_type_code", label: "Document type", width: "medium" },
  { name: "reference_number", label: "Reference number", width: "medium" },
  { name: "external_url", label: "Link" },
  { name: "notes", label: "Notes", kind: "textarea" },
];

/**
 * Document *references*, deliberately named as such.
 *
 * Nothing here uploads, stores or versions a file. Each row says which evidence
 * supports a record and where to find it, so the register is compact: a title,
 * a type, a reference, what it supports, and the way out to where it is held.
 */
export function DocumentsTab({
  projectId,
  canWrite,
}: {
  projectId: string;
  canWrite: boolean;
}) {
  const [rows, setRows] = useState<DocumentReference[] | null>(null);
  const [types, setTypes] = useState<ReferenceValue[]>([]);
  const [parcels, setParcels] = useState<LandParcel[]>([]);
  const [permits, setPermits] = useState<Permit[]>([]);
  const [form, setForm] = useState({
    title: "",
    document_type_code: "",
    external_url: "",
    reference_number: "",
    attach_to: "",
  });
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<DocumentReference | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setRows(await projects.documents(projectId));
      setError(null);
    } catch (caught) {
      setRows([]);
      setError(caught instanceof ApiError ? caught.message : "Could not load documents.");
    }
  }, [projectId]);

  useEffect(() => {
    void (async () => {
      await load();
    })();
  }, [load]);

  useEffect(() => {
    void (async () => {
      try {
        const [values, parcelList, register] = await Promise.all([
          settings.referenceValues(),
          projects.parcels(projectId),
          projects.permits(projectId),
        ]);
        setTypes(values.filter((value) => value.is_active && value.category === "document_type"));
        setParcels(parcelList);
        setPermits(register.permits);
      } catch {
        // Only the create form and the "supports" column need these.
      }
    })();
  }, [projectId]);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const payload: Record<string, unknown> = {
        title: form.title,
        document_type_code: form.document_type_code,
        external_url: form.external_url,
      };
      if (form.reference_number) payload.reference_number = form.reference_number;
      // One attachment at most: a reference that supports two records answers
      // "which record" with neither.
      if (form.attach_to.startsWith("parcel:")) {
        payload.parcel_id = form.attach_to.slice("parcel:".length);
      } else if (form.attach_to.startsWith("permit:")) {
        payload.permit_id = form.attach_to.slice("permit:".length);
      }
      await projects.createDocument(projectId, payload);
      setNotice("Document reference recorded.");
      setForm({ title: "", document_type_code: "", external_url: "", reference_number: "", attach_to: "" });
      setCreating(false);
      await load();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not record the reference.");
    } finally {
      setBusy(false);
    }
  };

  const retire = async (document: DocumentReference) => {
    try {
      await projects.updateDocument(projectId, document.id, { is_active: !document.is_active });
      await load();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not update the reference.");
    }
  };

  const typeLabel = (code: string) => types.find((value) => value.code === code)?.label ?? code;

  const attachment = (document: DocumentReference) => {
    if (document.parcel_id) {
      const parcel = parcels.find((item) => item.id === document.parcel_id);
      return parcel ? `Plot ${parcel.plot_number}` : "Parcel";
    }
    if (document.permit_id) {
      const permit = permits.find((item) => item.id === document.permit_id);
      return permit ? permit.permit_code : "Permit";
    }
    return "Project";
  };

  return (
    <>
      <PageHeader
        title="Documents"
        subtitle={sectionDescription("documents")}
        compact
        actions={
          canWrite ? (
            <Button variant="primary" onClick={() => setCreating((open) => !open)}>
              {creating ? "Cancel" : "New reference"}
            </Button>
          ) : undefined
        }
      />

      <div className="stack">
        {error ? <Notice tone="error">{error}</Notice> : null}
        {notice ? <Notice tone="success">{notice}</Notice> : null}

        {editing ? (
          <Card title="Edit reference" description={editing.title}>
            <EditForm
              fields={DOCUMENT_FIELDS}
              submitLabel="Save reference"
              initial={Object.fromEntries(
                DOCUMENT_FIELDS.map((field) => [
                  field.name,
                  asValue(editing[field.name as keyof DocumentReference] as never),
                ]),
              )}
              onSave={async (changes) => {
                await projects.updateDocument(projectId, editing.id, changes);
                await load();
                setNotice("Reference updated.");
              }}
              onCancel={() => setEditing(null)}
            />
          </Card>
        ) : null}

        {creating ? (
          <Card
            title="New document reference"
            description="A pointer to a document held elsewhere. The file itself is never uploaded here."
          >
            <form onSubmit={submit}>
              <FieldRow columns={3}>
                <Field label="Title">
                  <input
                    className="input"
                    required
                    value={form.title}
                    onChange={(event) => setForm({ ...form, title: event.target.value })}
                  />
                </Field>
                <Field label="Document type">
                  <select
                    className="input"
                    required
                    value={form.document_type_code}
                    onChange={(event) => setForm({ ...form, document_type_code: event.target.value })}
                  >
                    <option value="">Choose…</option>
                    {types.map((value) => (
                      <option key={value.id} value={value.code}>
                        {value.label}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Reference number" optional>
                  <input
                    className="input"
                    value={form.reference_number}
                    onChange={(event) => setForm({ ...form, reference_number: event.target.value })}
                  />
                </Field>
                <Field label="Link" hint="A web address where the document is held." className="field-span-2">
                  <input
                    className="input"
                    type="url"
                    required
                    value={form.external_url}
                    onChange={(event) => setForm({ ...form, external_url: event.target.value })}
                  />
                </Field>
                <Field label="Supports" hint="The project, or one parcel or permit.">
                  <select
                    className="input"
                    value={form.attach_to}
                    onChange={(event) => setForm({ ...form, attach_to: event.target.value })}
                  >
                    <option value="">The project</option>
                    {parcels.map((parcel) => (
                      <option key={parcel.id} value={`parcel:${parcel.id}`}>
                        Plot {parcel.plot_number}
                      </option>
                    ))}
                    {permits.map((permit) => (
                      <option key={permit.id} value={`permit:${permit.id}`}>
                        {permit.permit_code}
                      </option>
                    ))}
                  </select>
                </Field>
              </FieldRow>
              <FormActions>
                <Button variant="primary" type="submit" disabled={busy}>
                  {busy ? "Saving…" : "Record reference"}
                </Button>
                <Button onClick={() => setCreating(false)} disabled={busy}>
                  Cancel
                </Button>
              </FormActions>
            </form>
          </Card>
        ) : null}

        <Card flush>
          {rows === null ? (
            <Loading label="Loading references…" shape="rows" rows={4} />
          ) : rows.length === 0 ? (
            <div className="card-body">
              <EmptyState
                title="No document references"
                hint="Point at the deeds, drawings and approvals that support this project's records. The documents stay where they are held."
              />
            </div>
          ) : (
            <TableScroll label="Document references">
              <thead>
                <tr>
                  <th scope="col">Document</th>
                  <th scope="col">Type</th>
                  <th scope="col">Reference</th>
                  <th scope="col">Supports</th>
                  <th scope="col">State</th>
                  <th scope="col">
                    <span className="visually-hidden">Open</span>
                  </th>
                  {canWrite ? (
                    <th scope="col">
                      <span className="visually-hidden">Actions</span>
                    </th>
                  ) : null}
                </tr>
              </thead>
              <tbody>
                {rows.map((document) => (
                  <tr key={document.id}>
                    <th scope="row" className="cell-prose">
                      {document.title}
                      {document.notes ? <span className="cell-secondary">{document.notes}</span> : null}
                    </th>
                    <td>{typeLabel(document.document_type_code)}</td>
                    <td className="mono">{document.reference_number ?? "—"}</td>
                    <td>{attachment(document)}</td>
                    <td>
                      {document.is_active ? (
                        <StatusDot tone="success">Current</StatusDot>
                      ) : (
                        <StatusDot tone="muted">Superseded</StatusDot>
                      )}
                    </td>
                    <td>
                      <a
                        className="button button-small button-quiet"
                        href={document.external_url}
                        target="_blank"
                        rel="noreferrer noopener"
                      >
                        Open <Icon name="external" />
                      </a>
                    </td>
                    {canWrite ? (
                      <td>
                        <div className="row-actions">
                          <Button small variant="quiet" onClick={() => setEditing(document)}>
                            Edit
                          </Button>
                          <Button small variant="quiet" onClick={() => void retire(document)}>
                            {document.is_active ? "Supersede" : "Restore"}
                          </Button>
                        </div>
                      </td>
                    ) : null}
                  </tr>
                ))}
              </tbody>
            </TableScroll>
          )}
        </Card>
      </div>
    </>
  );
}
