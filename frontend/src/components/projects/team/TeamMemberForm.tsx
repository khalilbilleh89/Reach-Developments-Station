"use client";

import { useState } from "react";
import { ApiError } from "@/lib/api";
import { team, type TeamFields, type TeamKind, type TeamMember } from "@/lib/api/team";
import { Button, DraftBoundary, Field, FieldRow, FormActions, FormSection, RecordPage, ValidationSummary } from "@/components/ui";

export function TeamMemberForm({ projectId, initialTeam, member, onSaved, onClose }: {
  projectId: string; initialTeam: TeamKind; member?: TeamMember;
  onSaved: (name: string) => void; onClose: () => void;
}) {
  const [original] = useState(() => ({ team: member?.team ?? initialTeam, name: member?.name ?? "",
    title: member?.title ?? "", scope_of_work: member?.scope_of_work ?? "", email: member?.email ?? "" }));
  const [values, setValues] = useState(original);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | string | null>(null);
  const change = (key: keyof typeof values, value: string) => setValues(previous => ({ ...previous, [key]: value }));
  return <RecordPage eyebrow="PROJECT TEAM" icon="user" title={member ? "Edit team member" : "Add team member"}
    subtitle="Keep the right people, responsibilities and contact details together." onClose={onClose}>
    <DraftBoundary dirty={JSON.stringify(original) !== JSON.stringify(values)} busy={busy}>
      <form className="stack" onSubmit={async event => {
        event.preventDefault();
        if (busy) return;
        if (!values.name.trim()) { setError("Enter the person's name."); return; }
        setBusy(true); setError(null);
        const body: TeamFields = { ...values, name: values.name.trim(), title: values.title.trim() || null,
          scope_of_work: values.scope_of_work.trim() || null, email: values.email.trim() || null };
        try {
          const saved = member ? await team.update(projectId, member, body) : await team.create(projectId, body);
          onSaved(saved.name);
        } catch (caught) { setError(caught instanceof ApiError ? caught : "Could not save. Your entries have been kept."); }
        finally { setBusy(false); }
      }}>
        <ValidationSummary error={error} />
        <fieldset disabled={busy} className="team-fields">
          <FormSection title="Person & team" description="Choose a team and enter a name. You can complete the other details now or later.">
            <Field label="Team"><select name="team" value={values.team} onChange={event => change("team", event.target.value)}>
              <option value="operations">Operations Team</option><option value="engineering">Engineering Team</option>
            </select></Field>
            <FieldRow>
              <Field label="Name"><input name="name" autoComplete="name" required value={values.name} onChange={event => change("name", event.target.value)} /></Field>
              <Field label="Title" optional><input name="title" autoComplete="organization-title" value={values.title} onChange={event => change("title", event.target.value)} /></Field>
            </FieldRow>
          </FormSection>
          <FormSection title="Responsibilities & contact" description="Describe what this person handles so everyone knows who to contact.">
            <Field label="Scope of Work" optional><textarea name="scope_of_work" rows={6} value={values.scope_of_work} onChange={event => change("scope_of_work", event.target.value)} /></Field>
            <Field label="Email Address" optional><input name="email" type="email" autoComplete="email" value={values.email} onChange={event => change("email", event.target.value)} /></Field>
          </FormSection>
        </fieldset>
        <FormActions>
          <Button type="submit" disabled={busy}>{busy ? "Saving…" : member ? "Save changes" : "Add team member"}</Button>
          <Button variant="default" disabled={busy} data-leaves-editor onClick={onClose}>Cancel</Button>
        </FormActions>
      </form>
    </DraftBoundary>
  </RecordPage>;
}
