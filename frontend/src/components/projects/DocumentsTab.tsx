"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, projects, settings } from "@/lib/api";
import type { DocumentReference, LandParcel, Permit, ReferenceValue } from "@/lib/api";
import { Badge, EmptyState, Field, Loading, Notice, Panel } from "@/components/ui";

/**
 * Document *references*, deliberately named as such.
 *
 * Nothing here uploads, stores or versions a file. Each row says which evidence
 * supports a record and where to find it.
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
        setTypes(
          values.filter((value) => value.is_active && value.category === "document_type"),
        );
        setParcels(parcelList);
        setPermits(register.permits);
      } catch {
        // Only the create form needs these.
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
      setForm({
        title: "",
        document_type_code: "",
        external_url: "",
        reference_number: "",
        attach_to: "",
      });
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
    <Panel
      title="Document references"
      description="Links to documents held elsewhere. Nothing is uploaded or stored here."
      actions={
        canWrite ? (
          <button
            className="button button-small"
            type="button"
            onClick={() => setCreating((open) => !open)}
          >
            {creating ? "Cancel" : "New reference"}
          </button>
        ) : undefined
      }
    >
      {error ? <Notice tone="error">{error}</Notice> : null}
      {notice ? <Notice tone="success">{notice}</Notice> : null}

      {creating ? (
        <form className="panel-section" onSubmit={submit}>
          <div className="form-grid">
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
                onChange={(event) =>
                  setForm({ ...form, document_type_code: event.target.value })
                }
              >
                <option value="">Choose…</option>
                {types.map((value) => (
                  <option key={value.id} value={value.code}>
                    {value.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Link" hint="A web address where the document is held.">
              <input
                className="input"
                type="url"
                required
                value={form.external_url}
                onChange={(event) => setForm({ ...form, external_url: event.target.value })}
              />
            </Field>
            <Field label="Reference number">
              <input
                className="input"
                value={form.reference_number}
                onChange={(event) =>
                  setForm({ ...form, reference_number: event.target.value })
                }
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
          </div>
          <div className="form-actions">
            <button className="button button-primary" type="submit" disabled={busy}>
              {busy ? "Saving…" : "Record reference"}
            </button>
          </div>
        </form>
      ) : null}

      {rows === null ? (
        <Loading label="Loading references…" />
      ) : rows.length === 0 ? (
        <EmptyState
          title="No document references"
          hint="Point at the deeds, drawings and approvals that support this project's records."
        />
      ) : (
        <div className="table-scroll">
          <table className="table">
            <caption className="visually-hidden">Document references</caption>
            <thead>
              <tr>
                <th scope="col">Title</th>
                <th scope="col">Type</th>
                <th scope="col">Reference</th>
                <th scope="col">Supports</th>
                <th scope="col">Link</th>
                <th scope="col">State</th>
                {canWrite ? <th scope="col">Action</th> : null}
              </tr>
            </thead>
            <tbody>
              {rows.map((document) => (
                <tr key={document.id}>
                  <th scope="row">{document.title}</th>
                  <td>{document.document_type_code}</td>
                  <td>{document.reference_number ?? "—"}</td>
                  <td>{attachment(document)}</td>
                  <td>
                    <a href={document.external_url} target="_blank" rel="noreferrer noopener">
                      Open
                    </a>
                  </td>
                  <td>
                    {document.is_active ? (
                      <Badge tone="success">Current</Badge>
                    ) : (
                      <Badge tone="muted">Superseded</Badge>
                    )}
                  </td>
                  {canWrite ? (
                    <td>
                      <button
                        className="button button-small"
                        type="button"
                        onClick={() => void retire(document)}
                      >
                        {document.is_active ? "Supersede" : "Restore"}
                      </button>
                    </td>
                  ) : null}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}
