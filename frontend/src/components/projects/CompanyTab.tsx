"use client";

import { useState } from "react";
import { businessDate, decimalText } from "@/lib/format";
import { sectionIcon } from "@/components/shell/navigation";
import { ApiError, settings } from "@/lib/api";
import { companies, type Company, type CompanyFields, type BankFields, type BankAccount } from "@/lib/api/companies";
import { useAnswer } from "@/lib/answer";
import { hasAnyRole, PROJECT_FINANCIAL_READERS } from "@/lib/roles";
import { Badge, Button, Card, DraftBoundary, EmptyState, Field, FieldRow, FormActions, FormOutline, FormSection, KeyValue, KeyValueGrid, Loading, Notice, PageHeader, RecordPage, RecordStrip, RowMenu, Segmented, SectionHeader, StickyActions, SubPanel } from "@/components/ui";
import { CompanyLogoActions, CompanyLogoTile } from "./CompanyLogo";
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
  ["beneficiary_name", "Beneficiary name"],
  ["beneficiary_bank", "Beneficiary bank"],
  ["account_number", "Account number"],
  ["iban", "IBAN"],
  ["swift_code", "SWIFT code"],
  ["bank_address", "Bank address"],
  ["correspondent_bank", "Correspondent bank"],
  ["correspondent_swift_code", "Correspondent bank SWIFT"],
  ["account_purpose", "Account purpose"], ["currency_code", "Account currency"],
  ["default_for_payments", "Default for payments"], ["last_verified_date", "Last verified"],
  ["status", "Account status"], ["bank_country", "Bank country"],
];
const WRITERS = new Set(["system_admin", "project_manager", "finance"]);
const NO_RELATED_COMPANY = "none";
const NO_RELATED_COMPANY_LABEL = "No parent or related company";

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
  if (key === "ownership_percentage") return `${decimalText(String(value))}%`;
  return OPTIONS[key]?.find(([code]) => code === String(value))?.[1] ?? String(value);
}

/** Short fixed lists are segmented choices, not dropdowns (design system J2); "Not entered" keeps the value clearable. */
const SEGMENTED = new Set(["status", "default_for_payments", "account_purpose"]);
/** References a reader copies digit for digit. */
const MONO = new Set(["registration_number", "tax_number", "account_number", "iban", "swift_code", "correspondent_swift_code"]);
const entered = (value: unknown) => value !== null && value !== undefined && value !== "";

/**
 * One group of a company's or an account's recorded details: what was entered,
 * at full weight, and what was not, named once in muted text — never a column
 * of "Not entered" values competing with the facts that exist.
 */
export function RecordedDetails({ fields, record, rows }: { fields: [string, string][]; record: Record<string, unknown>; rows?: Company[] }) {
  const present = fields.filter(([key]) => entered(record[key]));
  const missing = fields.filter(([key]) => !entered(record[key]));
  return <>
    {present.length ? <KeyValueGrid>{present.map(([key, label]) => <KeyValue key={key} label={label} mono={MONO.has(key)} value={key === "notes" || key.endsWith("address") ? <span className="company-notes">{String(record[key])}</span> : display(key, record[key], rows)} />)}</KeyValueGrid> : null}
    {missing.length ? <p className="muted company-missing">{present.length ? "Not entered" : "Nothing entered yet"}: {missing.map(([, label]) => label).join(", ")}.</p> : null}
  </>;
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
/** The profile's reading groups. Ownership, role and relationship lead in the strip; status and name lead in the head. */
const COMPANY_DETAIL_GROUPS = [
  { title: "Identity & registration", keys: ["legal_name", "trading_name", "registration_number", "tax_number", "legal_form", "country", "incorporation_date"] },
  { title: "Address & contacts", keys: ["registered_address", "contact_name", "email", "phone", "website", "authorized_signatory"] },
];
/** Shown as the account's state line rather than repeated in its details. */
const BANK_STATE_KEYS = new Set(["default_for_payments", "status", "currency_code", "account_purpose"]);
const companyName = (row: Company) => row.legal_name || row.trading_name || "Unnamed company";
const PARENT_FIELDS = COMPANY_FIELDS.filter(([key]) => !COMPANY_GROUPS[1].keys.includes(key));
type EntryValues = Record<string, string | null>;
type CompanyEntryValues = EntryValues & { no_related_company?: boolean };

function entryFields(fields: [string, string][], values: Record<string, string>, setValues: (values: Record<string, string>) => void, busy: boolean, options: Record<string, [string, string][]>) {
  return <FieldRow>{fields.filter(([key]) => key !== "other_role" || values.project_role === "other" || values.other_role).map(([key, label]) => <Field key={key} label={label} optional
    hint={key === "relationship" ? "Describe this company’s relationship to the company selected below. Choose Subsidiary when linking to its parent." : undefined}>
    {SEGMENTED.has(key) ? <Segmented label={label} value={values[key]} onChange={value => { if (!busy) setValues({ ...values, [key]: value }); }}
      options={[{ value: "", label: "Not entered" }, ...(options[key] ?? OPTIONS[key]).map(([code, text]) => ({ value: code, label: text }))]} />
    : key === "related_company_id" || options[key] || OPTIONS[key] ? <select className="input" value={values[key]} disabled={busy} onChange={event => setValues({ ...values, [key]: event.target.value })}>
      <option value="" hidden={key === "related_company_id"}>Not entered</option>
      {key === "related_company_id" ? <option value={NO_RELATED_COMPANY}>{NO_RELATED_COMPANY_LABEL}</option> : null}
      {(options[key] ?? OPTIONS[key] ?? []).map(([code, text]) => <option key={code} value={code}>{text}</option>)}
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
      <FormActions><Button type="button" variant="primary" disabled={busy} onClick={async () => {
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
  onSave: (values: CompanyEntryValues) => Promise<unknown>; onClose: () => void;
}) {
  const [original] = useState(() => Object.fromEntries(fields.map(([key]) => {
    if (key === "related_company_id" && (initial as Partial<CompanyFields> | undefined)?.no_related_company) return [key, NO_RELATED_COMPANY];
    const value = String((initial as Record<string, unknown> | undefined)?.[key] ?? "");
    return [key, key === "ownership_percentage" && value ? decimalText(value) : value];
  })));
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
  const dirty = JSON.stringify(values) !== JSON.stringify(original);
  // A long form, three titled sections or more, gets section links and a save bar that stays in view (J3).
  const long = groups.length >= 3;
  return <RecordPage icon={groups === COMPANY_GROUPS ? "inventory" : undefined} title={title} subtitle="All fields are optional. Enter the information available now." onClose={onClose}>
    <DraftBoundary dirty={dirty} busy={busy}>
      <form className={long ? "form-layout" : "stack"} onSubmit={async event => {
        event.preventDefault();
        if (busy || relatedEditor) return;
        setBusy(true); setError(null);
        try {
          const payload: CompanyEntryValues = Object.fromEntries(fields.map(([key]) => [key, values[key].trim() || null]));
          if (fields.some(([key]) => key === "related_company_id")) {
            payload.no_related_company = values.related_company_id === NO_RELATED_COMPANY;
            if (payload.no_related_company) payload.related_company_id = null;
          }
          await onSave(payload);
          onClose();
        } catch (caught) { setError(caught instanceof ApiError ? caught.message : "Could not save. Your entries have been kept."); }
        finally { setBusy(false); }
      }}>
        {long ? <FormOutline sections={groups.map(group => group.title)} /> : null}
        <div className={long ? "form-layout-body stack" : "stack"}>
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
              setSavedRelated(rows => [...rows.filter(row => row.id !== saved.id), saved]);
              setValues(current => ({ ...current, related_company_id: saved.id }));
              setRelatedNotice("Parent company saved in the register. Save this company to confirm the link; cancelling this form will keep the parent company in the register.");
            }} />}
          </div> : null}
        </FormSection>)}
        {long ? <StickyActions dirty={dirty} submitLabel="Save company" busy={busy} disabled={relatedEditor !== null} note={relatedEditor ? "Save or cancel the parent company first." : undefined} onCancel={onClose} />
          : <FormActions><Button type="submit" variant="primary" disabled={busy || relatedEditor !== null}>{busy ? "Saving…" : "Save"}</Button>
            <Button variant="default" data-leaves-editor onClick={onClose} disabled={busy}>Cancel</Button>
          </FormActions>}
        </div>
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
  const roleText = selected ? selected.project_role === "other" && selected.other_role ? selected.other_role : selected.project_role ? display("project_role", selected.project_role) : null : null;
  const notEntered = (label: string) => ({ label, value: "Not entered", tone: "muted" as const });
  return <div className="stack">
    <PageHeader icon={sectionIcon("company")} title="Company" subtitle="The legal entities behind this project: registration, documents and bank accounts." actions={canWrite ? <Button variant="primary" onClick={() => setEditor({ kind: "company" })}>Add company</Button> : undefined} />
    {answer.status === "loading" ? <Loading label="Loading company details…" /> : null}
    {answer.status === "off" || answer.status === "denied" ? <Notice tone="info">Company details are not available to your access level.</Notice> : null}
    {answer.status === "failed" ? <Notice tone="error">{answer.message} <Button variant="default" onClick={answer.retry}>Retry</Button></Notice> : null}
    {answer.status === "ready" && !selected ? <Card><EmptyState title="No company recorded" hint="Add the developer, landowner, investor or project company, then record its documents and bank accounts. All entry fields are optional." /></Card> : null}
    {selected ? <>
      {rows.length > 1 ? <Field label={`Company · ${rows.length} in this project`}><select className="input" value={selected.id} onChange={event => setSelectedId(event.target.value)}>
        {rows.map(row => <option key={row.id} value={row.id}>{name(row)}</option>)}
      </select></Field> : null}
      <Card>
        <header className="company-identity">
          <CompanyLogoTile projectId={projectId} company={selected} />
          <div className="company-identity-main">
            <h2 className="company-identity-name">{name(selected)}</h2>
            {selected.legal_name && selected.trading_name && selected.trading_name !== selected.legal_name ? <p className="company-identity-meta">Trading as {selected.trading_name}</p> : null}
            <div className="company-identity-state">
              {selected.status ? <Badge tone={selected.status === "active" ? "success" : selected.status === "under_review" ? "warning" : "muted"}>{display("status", selected.status)}</Badge> : <span className="muted">Status not entered</span>}
            </div>
          </div>
          {canWrite ? <div className="card-actions">
            <Button onClick={() => setEditor({ kind: "company", row: selected })}>Edit company</Button>
            <RowMenu label={`More actions for ${name(selected)}`}>
              <CompanyLogoActions key={`${selected.id}-${selected.logo_id ?? "none"}`} projectId={projectId} company={selected} onSaved={answer.retry} />
              <DeleteRecordButton label="company" recordName={name(selected)} confirmLabel="Delete company"
                description="Remove this company from the register and retain its history. Remove its bank accounts, documents and logo, and unlink related companies first."
                onDelete={reason => companies.remove(projectId, selected.id, reason)} onDeleted={refresh} />
            </RowMenu>
          </div> : null}
        </header>
        <RecordStrip
          lead={entered(selected.ownership_percentage) ? { label: "Ownership share in project", value: display("ownership_percentage", selected.ownership_percentage) } : notEntered("Ownership share in project")}
          items={[
            roleText ? { label: "Role in the project", value: roleText } : notEntered("Role in the project"),
            selected.relationship ? { label: "Relationship", value: display("relationship", selected.relationship) } : notEntered("Relationship"),
            related ? { label: "Parent or related company", value: <Button variant="link" onClick={() => setSelectedId(related.id)}>{name(related)}</Button> }
              : selected.no_related_company ? { label: "Parent or related company", value: NO_RELATED_COMPANY_LABEL }
              : selected.related_company_id ? { label: "Parent or related company", value: "Linked company" }
              : notEntered("Parent or related company"),
          ]} />
        <div className="split split-even company-details">
          {COMPANY_DETAIL_GROUPS.map(group => <section key={group.title}>
            <SectionHeader title={group.title} />
            <RecordedDetails rows={rows} record={selected as unknown as Record<string, unknown>}
              fields={COMPANY_FIELDS.filter(([key]) => group.keys.includes(key) && !(key === "legal_name" && selected.legal_name) && !(key === "trading_name" && !selected.legal_name && selected.trading_name))} />
          </section>)}
        </div>
        {selected.notes ? <section className="company-notes-section"><SectionHeader title="Notes" /><p className="company-notes">{selected.notes}</p></section> : null}
      </Card>
      <CompanyDocuments key={selected.id} projectId={projectId} companyId={selected.id} canWrite={canWrite} />
      {canBank ? <Card>
        <SectionHeader level={2} title="Bank accounts" description={selected.bank_accounts.length ? `${selected.bank_accounts.length} recorded for ${name(selected)}.` : undefined} actions={<Button onClick={() => setEditor({ kind: "bank", companyId: selected.id })}>Add bank account</Button>} />
        {selected.bank_accounts.length === 0 ? <EmptyState title="No bank accounts recorded" hint="You can add multiple accounts for this company." /> :
          <div className="stack">{selected.bank_accounts.map((account, index) => <SubPanel key={account.id} title={account.beneficiary_bank || `Bank account ${index + 1}`} actions={<>
              <Button onClick={() => setEditor({ kind: "bank", companyId: selected.id, row: account })}>Edit account</Button>
              <RowMenu label={`More actions for ${account.beneficiary_bank || `bank account ${index + 1}`}`}>
                <DeleteRecordButton label="bank account" recordName={account.beneficiary_bank || `Bank account ${index + 1}`} confirmLabel="Delete bank account"
                  description="Remove this account from the company. Its details and audit history will be retained."
                  onDelete={reason => companies.removeBank(projectId, selected.id, account.id, reason)} onDeleted={refresh} />
              </RowMenu>
            </>}>
            <div className="company-account-state">
              {account.default_for_payments ? <Badge tone="accent">Default for payments</Badge> : null}
              {account.status ? <Badge tone={account.status === "active" ? "success" : "muted"}>{display("status", account.status)}</Badge> : null}
              {account.currency_code ? <Badge>{account.currency_code}</Badge> : null}
              {account.account_purpose ? <span>{display("account_purpose", account.account_purpose)} account</span> : null}
            </div>
            <RecordedDetails record={account as unknown as Record<string, unknown>} fields={BANK_FIELDS.filter(([key]) => !BANK_STATE_KEYS.has(key) && !(key === "beneficiary_bank" && account.beneficiary_bank))} />
          </SubPanel>)}</div>}
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

