"use client";

import { useState } from "react";
import { ApiError } from "@/lib/api";
import { team, type TeamMember } from "@/lib/api/team";
import { Button, DraftBoundary, Field, FormActions, FormSection, RecordPage, ValidationSummary } from "@/components/ui";
import { DeleteRecordButton } from "../DeleteRecordButton";

export function TeamJobDescription({ projectId, member, onSaved, onClose }: {
  projectId: string; member: TeamMember; onSaved: () => void; onClose: () => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | string | null>(null);
  return <RecordPage eyebrow={member.name} title="Job Description" icon="user"
    subtitle="Optional supporting document for this team member." onClose={onClose}>
    <DraftBoundary dirty={file !== null} busy={busy}>
      <form className="stack" onSubmit={async event => {
        event.preventDefault();
        if (busy || !file) return;
        if (!file.size || file.size > 10 * 1024 * 1024 || !/\.(pdf|doc|docx)$/i.test(file.name)) {
          setError("Choose a non-empty PDF or Word document up to 10 MB."); return;
        }
        setBusy(true); setError(null);
        try { await team.uploadDocument(projectId, member, file); onSaved(); }
        catch (caught) { setError(caught instanceof ApiError ? caught : "Could not upload. Your file selection has been kept; try again."); }
        finally { setBusy(false); }
      }}>
        <ValidationSummary error={error} />
        <FormSection title="Job Description" description="PDF or Word (.pdf, .doc, .docx), up to 10 MB. Adding this file is optional.">
          <p className="muted">{member.job_description ? `Current file: ${member.job_description.filename}` : "No job description attached."}</p>
          {member.job_description ? <p className="muted">Saving a replacement keeps the previous file in retained history.</p> : null}
          <Field label={member.job_description ? "Replacement file" : "Attachment"} optional>
            <input className="input" name="job_description" type="file" accept=".pdf,.doc,.docx" disabled={busy}
              onChange={event => { setFile(event.target.files?.[0] ?? null); setError(null); }} />
          </Field>
          {file ? <p>{file.name} ready to upload.</p> : null}
        </FormSection>
        <FormActions>
          <Button type="submit" disabled={busy || !file}>{busy ? "Working..." : member.job_description ? "Replace job description" : "Upload job description"}</Button>
          <Button variant="default" disabled={busy} data-leaves-editor onClick={onClose}>Cancel</Button>
        </FormActions>
      </form>
      {member.job_description && !file ? <DeleteRecordButton label="job description" recordName={`${member.job_description.filename} for ${member.name}`}
        confirmLabel="Delete job description" destructive description="Remove this attachment from the team member. The file and audit history will be retained."
        onDelete={async reason => { setBusy(true); try { await team.removeDocument(projectId, member, reason); } finally { setBusy(false); } }}
        onDeleted={async () => onSaved()} /> : null}
    </DraftBoundary>
  </RecordPage>;
}
