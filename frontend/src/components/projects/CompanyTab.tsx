"use client";

import { useState } from "react";
import { ApiError } from "@/lib/api";
import { companies, type Company, type CompanyFields, type BankFields, type BankAccount } from "@/lib/api/companies";
import { useAnswer } from "@/lib/answer";
import { hasAnyRole, PROJECT_FINANCIAL_READERS } from "@/lib/roles";
import { Button, Card, DraftBoundary, EmptyState, Field, FieldRow, FormActions, KeyValue, KeyValueGrid, Loading, Notice, PageHeader, RecordPage, SectionHeader } from "@/components/ui";
import { DeleteRecordButton } from "./DeleteRecordButton";

export const COMPANY_FIELDS: [keyof CompanyFields, string][] = [
  ["legal_name", "Legal company name"],
  ["trading_name", "Trading name"],
  ["registration_number", "Registration number"],
  ["tax_number", "Tax / VAT number"],
  ["legal_form", "Legal form"],
  ["country", "Country of registration"],
  ["registered_address", "Registered address"],
  ["contact_name", "Contact person"],
  ["email", "Email"],
  ["phone", "Phone"],
  ["website", "Website"],
  ["authorized_signatory", "Authorized signatory"],
  ["notes", "Notes"],
];
export const BANK_FIELDS: [keyof BankFields, string][] = [
  ["beneficiary_name", "Beneficiary Name"],
  ["beneficiary_bank", "Beneficiary Bank"],
  ["account_number", "Account #"],
  ["iban", "IBAN"],
  ["swift_code", "SWIFT Code"],
  ["bank_address", "Bank Address"],
  ["correspondent_bank", "Correspondent Bank"],
  ["correspondent_swift_code", "Correspondent Bank SWIFT"],
];
const WRITERS = new Set(["system_admin", "project_manager", "finance"]);

export function CompanyEntryForm({ title, fields, initial, onSave, onClose }: {
  title: string; fields: [string, string][]; initial?: object;
  onSave: (values: Record<string, string | null>) => Promise<unknown>; onClose: () => void;
}) {
  const [original] = useState(() => Object.fromEntries(fields.map(([key]) => [key, String((initial as Record<string, unknown> | undefined)?.[key] ?? "")])));
  const [values, setValues] = useState(original);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return <RecordPage title={title} onClose={onClose}>
    <DraftBoundary dirty={JSON.stringify(values) !== JSON.stringify(original)} busy={busy}>
      <form className="stack" onSubmit={async event => {
        event.preventDefault();
        if (busy) return;
        setBusy(true); setError(null);
        try {
          await onSave(Object.fromEntries(fields.map(([key]) => [key, values[key].trim() || null])));
          onClose();
        } catch (caught) { setError(caught instanceof ApiError ? caught.message : "Could not save. Your entries have been kept."); }
        finally { setBusy(false); }
      }}>
        <p className="muted">All fields are optional. Enter the information available now.</p>
        {error ? <Notice tone="error">{error}</Notice> : null}
        <FieldRow>{fields.map(([key, label]) => <Field key={key} label={label} optional>
          {["notes", "registered_address", "bank_address"].includes(key)
            ? <textarea value={values[key]} maxLength={2000} onChange={event => setValues({ ...values, [key]: event.target.value })} />
            : <input type="text" value={values[key]} maxLength={320} onChange={event => setValues({ ...values, [key]: event.target.value })} />}
        </Field>)}</FieldRow>
        <FormActions><Button type="submit" disabled={busy}>{busy ? "Saving…" : "Save"}</Button>
          <Button variant="default" data-leaves-editor onClick={onClose} disabled={busy}>Cancel</Button>
        </FormActions>
      </form>
    </DraftBoundary>
  </RecordPage>;
}

export function CompanyTab({ projectId, roles }: { projectId: string; roles: Set<string> }) {
  const answer = useAnswer(hasAnyRole(roles, PROJECT_FINANCIAL_READERS), () => companies.list(projectId), [projectId]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [editor, setEditor] = useState<{ kind: "company"; row?: Company } | { kind: "bank"; companyId: string; row?: BankAccount } | null>(null);
  const canWrite = hasAnyRole(roles, WRITERS);
  const refresh = async () => { answer.retry(); };
  const rows = answer.status === "ready" ? answer.data : [];
  const selected = rows.find(row => row.id === selectedId) ?? rows[0];
  const name = (row: Company) => row.legal_name || row.trading_name || "Unnamed company";
  return <div className="stack">
    <PageHeader title="Company" subtitle="Company information and registered bank accounts." actions={canWrite ? <Button onClick={() => setEditor({ kind: "company" })}>Add company</Button> : undefined} />
    {answer.status === "loading" ? <Loading label="Loading company details…" /> : null}
    {answer.status === "off" || answer.status === "denied" ? <Notice tone="info">Company details are not available to your access level.</Notice> : null}
    {answer.status === "failed" ? <Notice tone="error">{answer.message} <Button variant="default" onClick={answer.retry}>Retry</Button></Notice> : null}
    {answer.status === "ready" && !selected ? <Card><EmptyState title="No company recorded" hint="Add a company, then record its bank accounts. All entry fields are optional." /></Card> : null}
    {selected ? <>
      {rows.length > 1 ? <Field label="Company"><select value={selected.id} onChange={event => setSelectedId(event.target.value)}>
        {rows.map(row => <option key={row.id} value={row.id}>{name(row)}</option>)}
      </select></Field> : null}
      <Card>
        <SectionHeader level={2} title="Company Information" actions={canWrite ? <>
          <Button variant="default" onClick={() => setEditor({ kind: "company", row: selected })}>Edit company</Button>
          <DeleteRecordButton label="company" recordName={name(selected)} confirmLabel="Delete company"
            description="Remove this company from the register and retain its history. Delete its bank accounts first."
            onDelete={reason => companies.remove(projectId, selected.id, reason)} onDeleted={refresh} />
        </> : undefined} />
        <KeyValueGrid>{COMPANY_FIELDS.map(([key, label]) => <KeyValue key={key} label={label} value={selected[key] || "Not entered"} />)}</KeyValueGrid>
      </Card>
      <Card>
        <SectionHeader level={2} title="Bank Details" actions={canWrite ? <Button onClick={() => setEditor({ kind: "bank", companyId: selected.id })}>Add bank account</Button> : undefined} />
        {selected.bank_accounts.length === 0 ? <EmptyState title="No bank accounts recorded" hint="You can add multiple accounts for this company." /> :
          <div className="stack">{selected.bank_accounts.map((account, index) => <section key={account.id} className="form-section">
            <SectionHeader title={account.beneficiary_bank || `Bank account ${index + 1}`} actions={canWrite ? <>
              <Button variant="default" onClick={() => setEditor({ kind: "bank", companyId: selected.id, row: account })}>Edit account</Button>
              <DeleteRecordButton label="bank account" recordName={account.beneficiary_bank || `Bank account ${index + 1}`} confirmLabel="Delete bank account"
                description="Remove this account from the company. Its details and audit history will be retained."
                onDelete={reason => companies.removeBank(projectId, selected.id, account.id, reason)} onDeleted={refresh} />
            </> : undefined} />
            <KeyValueGrid>{BANK_FIELDS.map(([key, label]) => <KeyValue key={key} label={label} value={account[key] || "Not entered"} />)}</KeyValueGrid>
          </section>)}</div>}
      </Card>
    </> : null}
    {editor ? <CompanyEntryForm key={editor.kind === "company" ? editor.row?.id ?? "new-company" : editor.row?.id ?? "new-account"}
      title={editor.kind === "company" ? editor.row ? "Edit company" : "Add company" : editor.row ? "Edit bank account" : "Add bank account"}
      fields={editor.kind === "company" ? COMPANY_FIELDS : BANK_FIELDS} initial={editor.row} onClose={() => setEditor(null)}
      onSave={async values => {
        if (editor.kind === "company") {
          const saved = editor.row ? await companies.update(projectId, editor.row.id, values) : await companies.create(projectId, values);
          setSelectedId(saved.id);
        } else if (editor.row) await companies.updateBank(projectId, editor.companyId, editor.row.id, values);
        else await companies.addBank(projectId, editor.companyId, values);
        answer.retry();
      }} /> : null}
  </div>;
}

