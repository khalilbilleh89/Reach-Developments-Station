"use client";

import { useState } from "react";
import { businessDate } from "@/lib/format";
import { sectionIcon } from "@/components/shell/navigation";
import { ApiError, settings } from "@/lib/api";
import { companies, type Company, type CompanyFields, type BankFields, type BankAccount } from "@/lib/api/companies";
import { useAnswer } from "@/lib/answer";
import { hasAnyRole, PROJECT_FINANCIAL_READERS } from "@/lib/roles";
import { Badge, Button, Card, DraftBoundary, EmptyState, Field, FieldRow, FormActions, FormSection, KeyValue, KeyValueGrid, Loading, Notice, PageHeader, RecordPage, SectionHeader, SubPanel } from "@/components/ui";
import { CompanyLogo } from "./CompanyLogo";
import { CompanyDocuments } from "./CompanyDocuments";
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
  ["project_role", "Company role in the project"],
  ["other_role", "Other role"],
  ["relationship", "Relationship to other companies"],
  ["related_company_id", "Parent or related company"],
  ["ownership_percentage", "Ownership share in project (%)"],
  ["incorporation_date", "Incorporation / registration date"],
  ["status", "Company status"],
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
  ["account_purpose", "Account purpose"], ["currency_code", "Account currency"],
  ["default_for_payments", "Default for payments"], ["last_verified_date", "Last verified"],
  ["status", "Account status"], ["bank_country", "Bank country"],
];
const WRITERS = new Set(["system_admin", "project_manager", "finance"]);

const OPTIONS: Record<string, [string, string][]> = {
  project_role: [["developer", "Developer"], ["landowner", "Landowner"], ["investor", "Investor"], ["project_company_spv", "Project company / SPV"], ["contractor", "Contractor"], ["other", "Other role"]],
  relationship: [["independent", "Independent"], ["parent_company", "Parent company"], ["subsidiary", "Subsidiary"], ["joint_venture", "Joint venture"], ["project_entity", "Project entity"]],
  account_purpose: [["project", "Project"], ["operating", "Operating"], ["escrow", "Escrow"], ["other", "Other"]],
  default_for_payments: [["true", "Yes"], ["false", "No"]],
  status: [["active", "Active"], ["inactive", "Inactive"], ["under_review", "Under review"]],
};
function display(key: string, value: unknown, rows: Company[] = []): string {
  if (value === null || value === undefined || value === "") return "Not entered";
  if (key === "related_company_id") { const related = rows.find(row => row.id === value); return related?.legal_name || related?.trading_name || "Linked company"; }
  if (key.endsWith("_date")) return businessDate(String(value));
  if (key === "ownership_percentage") return `${value}%`;
  return OPTIONS[key]?.find(([code]) => code === String(value))?.[1] ?? String(value);
}

const COMPANY_GROUPS = [
  { title: "Identity & registration", keys: ["legal_name", "trading_name", "registration_number", "tax_number", "legal_form", "country", "incorporation_date", "status"] },
  { title: "Project & ownership", keys: ["project_role", "other_role", "relationship", "related_company_id", "ownership_percentage"] },
  { title: "Address & contacts", keys: ["registered_address", "contact_name", "email", "phone", "website", "authorized_signatory"] },
  { title: "Notes", keys: ["notes"] },
];
const BANK_GROUPS = [
  { title: "Account information", keys: ["beneficiary_name", "beneficiary_bank", "account_number", "iban", "currency_code", "account_purpose", "default_for_payments", "status"] },
  { title: "Routing & verification", keys: ["swift_code", "bank_address", "bank_country", "correspondent_bank", "correspondent_swift_code", "last_verified_date"] },
];
const companyName = (row: Company) => row.legal_name || row.trading_name || "Unnamed company";
const PARENT_FIELDS = COMPANY_FIELDS.filter(([key]) => !COMPANY_GROUPS[1].keys.includes(key));
type EntryValues = Record<string, string | null>;

function entryFields(fields: [string, string][], values: Record<string, string>, setValues: (values: Record<string, string>) => void, busy: boolean, options: Record<string, [string, string][]>) {
  return <FieldRow>{fields.filter(([key]) => key !== "other_role" || values.project_role === "other" || values.other_role).map(([key, label]) => <Field key={key} label={label} optional
    hint={key === "relationship" ? "Describe this company’s relationship to the company selected below. Choose Subsidiary when linking to its parent." : undefined}>
    {options[key] || OPTIONS[key] ? <select className="input" value={values[key]} disabled={busy} onChange={event => setValues({ ...values, [key]: event.target.value })}>
      <option value="">Not entered</option>{(options[key] ?? OPTIONS[key]).map(([code, text]) => <option key={code} value={code}>{text}</option>)}
    </select> : ["notes", "registered_address", "bank_address"].includes(key)
      ? <textarea className="input" disabled={busy} rows={3} value={values[key]} maxLength={2000} onChange={event => setValues({ ...values, [key]: event.target.value })} />
      : <input className="input" type={key.endsWith("_date") ? "date" : "text"} inputMode={key === "ownership_percentage" ? "decimal" : undefined} disabled={busy} value={values[key]} maxLength={320} onChange={event => setValues({ ...values, [key]: event.target.value })} />}
  </Field>)}</FieldRow>;
}

export function RelatedCompanyEditor({ row, onSave, onClose, onBusy }: {
  row?: Company; onSave: (values: EntryValues) => Promise<unknown>; onClose: () => void; onBusy: (value: boolean) => void;
}) {
  const [original] = useState(() => Object.fromEntries(PARENT_FIELDS.map(([key]) => [key, String(row?.[key] ?? "")])));
  const [values, setValues] = useState(original);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return <DraftBoundary dirty={JSON.stringify(values) !== JSON.stringify(original)} busy={busy}>
    <SubPanel title={row ? "Edit parent / related company" : "New parent / related company"}>
      <p className="muted">Save these details to the company register, then save the company above to confirm the link. All fields are optional.</p>
      {error ? <Notice tone="error">{error}</Notice> : null}
      {COMPANY_GROUPS.filter(group => group.title !== "Project & ownership").map(group => <FormSection key={group.title} title={group.title}>
        {entryFields(PARENT_FIELDS.filter(([key]) => group.keys.includes(key)), values, setValues, busy, {})}
      </FormSection>)}
      <FormActions><Button type="button" disabled={busy} onClick={async () => {
        if (busy) return; setBusy(true); onBusy(true); setError(null);
        try { await onSave(Object.fromEntries(PARENT_FIELDS.map(([key]) => [key, values[key].trim() || null]))); onClose(); }
        catch (caught) { setError(caught instanceof ApiError ? caught.message : "Could not save the parent company. Your entries have been kept."); }
        finally { setBusy(false); onBusy(false); }
      }}>{busy ? "Saving…" : "Save parent company"}</Button>
        <Button variant="default" type="button" disabled={busy} data-leaves-editor onClick={onClose}>Cancel parent details</Button>
      </FormActions>
    </SubPanel>
  </DraftBoundary>;
}

export function CompanyEntryForm({ title, fields, initial, options = {}, relatedCompanies = [], onSaveRelated, onSave, onClose }: {
  title: string; fields: [string, string][]; initial?: object; options?: Record<string, [string, string][]>;
  relatedCompanies?: Company[]; onSaveRelated?: (values: EntryValues, row?: Company) => Promise<Company>;
  onSave: (values: Record<string, string | null>) => Promise<unknown>; onClose: () => void;
}) {
  const [original] = useState(() => Object.fromEntries(fields.map(([key]) => [key, String((initial as Record<string, unknown> | undefined)?.[key] ?? "")])));
  const [values, setValues] = useState(original);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [relatedEditor, setRelatedEditor] = useState<{ row?: Company } | null>(null);
  const [savedRelated, setSavedRelated] = useState<Company[]>([]);
  const [relatedNotice, setRelatedNotice] = useState<string | null>(null);
  const relatedRows = [...relatedCompanies.filter(row => !savedRelated.some(saved => saved.id === row.id)), ...savedRelated];
  const selectedRelated = relatedRows.find(row => row.id === values.related_company_id);
  const fieldOptions = { ...options, ...(onSaveRelated ? { related_company_id: relatedRows.map(row => [row.id, companyName(row)] as [string, string]) } : {}) };
  const groups = fields.some(([key]) => key === "legal_name") ? COMPANY_GROUPS : BANK_GROUPS;
  return <RecordPage title={title} onClose={onClose}>
    <DraftBoundary dirty={JSON.stringify(values) !== JSON.stringify(original)} busy={busy}>
      <form className="stack" onSubmit={async event => {
        event.preventDefault();
        if (busy || relatedEditor) return;
        setBusy(true); setError(null);
        try {
          await onSave(Object.fromEntries(fields.map(([key]) => [key, values[key].trim() || null])));
          onClose();
        } catch (caught) { setError(caught instanceof ApiError ? caught.message : "Could not save. Your entries have been kept."); }
        finally { setBusy(false); }
      }}>
        <p className="muted">All fields are optional. Enter the information available now.</p>
        {error ? <Notice tone="error">{error}</Notice> : null}
        {groups.map(group => <FormSection key={group.title} title={group.title}>
          {entryFields(fields.filter(([key]) => group.keys.includes(key)), values, setValues, busy, fieldOptions)}
          {group.title === "Project & ownership" && onSaveRelated ? <div className="stack company-relationship-tools">
            {!relatedRows.length ? <p className="muted">No other company has been added to this project yet. Add the parent company here, then save this company to link them.</p> : null}
            {relatedNotice ? <Notice tone="info">{relatedNotice}</Notice> : null}
            {!relatedEditor ? <>
              <div className="form-actions">
                <Button type="button" variant="default" disabled={busy} onClick={() => setRelatedEditor({})}>Add parent company</Button>
                {selectedRelated ? <Button type="button" variant="default" disabled={busy} onClick={() => setRelatedEditor({ row: selectedRelated })}>Edit parent company details</Button> : null}
              </div>
              {selectedRelated ? <KeyValueGrid><KeyValue label="Selected company" value={companyName(selectedRelated)} /><KeyValue label="Registration number" value={selectedRelated.registration_number || "Not entered"} /><KeyValue label="Country of registration" value={selectedRelated.country || "Not entered"} /><KeyValue label="Contact person" value={selectedRelated.contact_name || "Not entered"} /></KeyValueGrid> : null}
            </> : <RelatedCompanyEditor key={relatedEditor.row?.id ?? "new-parent"} row={relatedEditor.row} onClose={() => setRelatedEditor(null)} onBusy={setBusy} onSave={async parentValues => {
              const saved = await onSaveRelated(parentValues, relatedEditor.row);
              setSavedRelated([...savedRelated.filter(row => row.id !== saved.id), saved]);
              setValues({ ...values, related_company_id: saved.id });
              setRelatedNotice("Parent company saved in the register. Save this company to confirm the link; cancelling this form will keep the parent company in the register.");
            }} />}
          </div> : null}
        </FormSection>)}
        <FormActions><Button type="submit" disabled={busy || relatedEditor !== null}>{busy ? "Saving…" : "Save"}</Button>
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
  const canBank = hasAnyRole(roles, new Set(["system_admin", "finance"]));
  const currencies = useAnswer(canBank, settings.currencies, []);
  const canWrite = hasAnyRole(roles, WRITERS);
  const refresh = async () => { answer.retry(); };
  const rows = answer.status === "ready" ? answer.data : [];
  const selected = rows.find(row => row.id === selectedId) ?? rows[0];
  const name = companyName;
  const related = rows.find(row => row.id === selected?.related_company_id);
  return <div className="stack">
    <PageHeader icon={sectionIcon("company")} title="Company" subtitle="Company information, registration documents and registered bank accounts." actions={canWrite ? <Button onClick={() => setEditor({ kind: "company" })}>Add company</Button> : undefined} />
    {answer.status === "loading" ? <Loading label="Loading company details…" /> : null}
    {answer.status === "off" || answer.status === "denied" ? <Notice tone="info">Company details are not available to your access level.</Notice> : null}
    {answer.status === "failed" ? <Notice tone="error">{answer.message} <Button variant="default" onClick={answer.retry}>Retry</Button></Notice> : null}
    {answer.status === "ready" && !selected ? <Card><EmptyState title="No company recorded" hint="Add a company, then record its bank accounts. All entry fields are optional." /></Card> : null}
    {selected ? <>
      {rows.length > 1 ? <Field label="Company"><select className="input" value={selected.id} onChange={event => setSelectedId(event.target.value)}>
        {rows.map(row => <option key={row.id} value={row.id}>{name(row)}</option>)}
      </select></Field> : null}
      <Card>
        <SectionHeader level={2} title={name(selected)} description="Company Information" actions={canWrite ? <>
          <Button variant="default" onClick={() => setEditor({ kind: "company", row: selected })}>Edit company</Button>
          <DeleteRecordButton label="company" recordName={name(selected)} confirmLabel="Delete company"
            description="Remove this company from the register and retain its history. Remove its bank accounts, documents and logo, and unlink related companies first."
            onDelete={reason => companies.remove(projectId, selected.id, reason)} onDeleted={refresh} />
        </> : undefined} />
        <CompanyLogo key={selected.id} projectId={projectId} company={selected} canWrite={canWrite} onSaved={answer.retry} />
        <div className="company-profile-status"><Badge tone={selected.status === "active" ? "success" : "neutral"}>{display("status", selected.status)}</Badge>{selected.project_role ? <span>{display("project_role", selected.project_role)}</span> : null}{selected.country ? <span>{selected.country}</span> : null}</div>
        <div className="company-profile-sections">{COMPANY_GROUPS.map(group => <section key={group.title} className="company-profile-section">
          <SectionHeader title={group.title} actions={group.title === "Project & ownership" && related ? <Button variant="default" onClick={() => setSelectedId(related.id)}>Open parent / related company</Button> : undefined} />
          <KeyValueGrid>{COMPANY_FIELDS.filter(([key]) => group.keys.includes(key) && (key !== "other_role" || selected.other_role)).map(([key, label]) => <KeyValue key={key} label={label} value={display(key, selected[key], rows)} />)}</KeyValueGrid>
        </section>)}</div>
      </Card>
      <CompanyDocuments key={selected.id} projectId={projectId} companyId={selected.id} canWrite={canWrite} companyName={name(selected)} />
      {canBank ? <Card>
        <SectionHeader level={2} title="Bank Details" actions={canBank ? <Button onClick={() => setEditor({ kind: "bank", companyId: selected.id })}>Add bank account</Button> : undefined} />
        {selected.bank_accounts.length === 0 ? <EmptyState title="No bank accounts recorded" hint="You can add multiple accounts for this company." /> :
          <div className="stack">{selected.bank_accounts.map((account, index) => <section key={account.id} className="form-section">
            <SectionHeader title={account.beneficiary_bank || `Bank account ${index + 1}`} actions={canBank ? <>
              <Button variant="default" onClick={() => setEditor({ kind: "bank", companyId: selected.id, row: account })}>Edit account</Button>
              <DeleteRecordButton label="bank account" recordName={account.beneficiary_bank || `Bank account ${index + 1}`} confirmLabel="Delete bank account"
                description="Remove this account from the company. Its details and audit history will be retained."
                onDelete={reason => companies.removeBank(projectId, selected.id, account.id, reason)} onDeleted={refresh} />
            </> : undefined} />
            <KeyValueGrid>{BANK_FIELDS.map(([key, label]) => <KeyValue key={key} label={label} value={display(key, account[key])} />)}</KeyValueGrid>
          </section>)}</div>}
      </Card> : <Notice tone="info">Bank details are available to finance and administrators only.</Notice>}
    </> : null}
    {editor?.kind === "bank" && currencies.status === "failed" ? <Notice tone="error">Could not load currencies. <Button variant="default" onClick={currencies.retry}>Retry currencies</Button></Notice> : null}
    {editor ? <CompanyEntryForm key={editor.kind === "company" ? editor.row?.id ?? "new-company" : editor.row?.id ?? "new-account"}
      title={editor.kind === "company" ? editor.row ? "Edit company" : "Add company" : editor.row ? "Edit bank account" : "Add bank account"}
      options={{
        related_company_id: rows.filter(row => row.id !== editor.row?.id).map(row => [row.id, name(row)]),
        currency_code: currencies.status === "ready" ? currencies.data.map(row => [row.code, row.code]) : [],
        status: editor.kind === "bank" ? OPTIONS.status.filter(([code]) => code !== "under_review") : OPTIONS.status,
      }}
      relatedCompanies={rows.filter(row => row.id !== editor.row?.id)}
      onSaveRelated={editor.kind === "company" ? async (values, row) => {
        const saved = row ? await companies.update(projectId, row.id, values) : await companies.create(projectId, values);
        return saved;
      } : undefined}
      fields={editor.kind === "company" ? COMPANY_FIELDS : BANK_FIELDS} initial={editor.row} onClose={() => { setEditor(null); answer.retry(); }}
      onSave={async values => {
        if (editor.kind === "company") {
          const saved = editor.row ? await companies.update(projectId, editor.row.id, values) : await companies.create(projectId, values);
          setSelectedId(saved.id);
        } else if (editor.row) await companies.updateBank(projectId, editor.companyId, editor.row.id, { ...values, default_for_payments: values.default_for_payments === null ? null : values.default_for_payments === "true" });
        else await companies.addBank(projectId, editor.companyId, { ...values, default_for_payments: values.default_for_payments === null ? null : values.default_for_payments === "true" });
        answer.retry();
      }} /> : null}
  </div>;
}

