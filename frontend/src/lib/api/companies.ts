import { download, get, post, patch, postBinary } from "./client";

export interface CompanyFields {
  legal_name: string | null;
  trading_name: string | null;
  registration_number: string | null;
  tax_number: string | null;
  legal_form: string | null;
  country: string | null;
  registered_address: string | null;
  contact_name: string | null;
  email: string | null;
  phone: string | null;
  website: string | null;
  authorized_signatory: string | null;
  project_role: string | null;
  other_role: string | null;
  relationship: string | null;
  related_company_id: string | null;
  ownership_percentage: string | null;
  incorporation_date: string | null;
  status: string | null;
  notes: string | null;
}
export interface BankFields {
  beneficiary_name: string | null;
  beneficiary_bank: string | null;
  account_number: string | null;
  iban: string | null;
  swift_code: string | null;
  bank_address: string | null;
  correspondent_bank: string | null;
  correspondent_swift_code: string | null;
  account_purpose: string | null;
  currency_code: string | null;
  default_for_payments: boolean | null;
  last_verified_date: string | null;
  status: string | null;
  bank_country: string | null;
}
export interface BankAccount extends BankFields { id: string }
export interface Company extends CompanyFields { id: string; logo_id: string | null; bank_accounts: BankAccount[] }

const root = (projectId: string) => `/projects/${projectId}/companies`;
export const companies = {
  list: (projectId: string) => get<Company[]>(root(projectId)),
  create: (projectId: string, body: Partial<CompanyFields>) => post<Company>(root(projectId), { ...body }),
  update: (projectId: string, id: string, body: Partial<CompanyFields>) => patch<Company>(`${root(projectId)}/${id}`, { ...body }),
  remove: (projectId: string, id: string, reason: string) => post<void>(`${root(projectId)}/${id}/delete`, { reason }),
  addBank: (projectId: string, id: string, body: Partial<BankFields>) => post<BankAccount>(`${root(projectId)}/${id}/bank-accounts`, { ...body }),
  updateBank: (projectId: string, id: string, accountId: string, body: Partial<BankFields>) => patch<BankAccount>(`${root(projectId)}/${id}/bank-accounts/${accountId}`, { ...body }),
  removeBank: (projectId: string, id: string, accountId: string, reason: string) => post<void>(`${root(projectId)}/${id}/bank-accounts/${accountId}/delete`, { reason }),
};


export interface DocumentMetadata {
  category?: string | null; linked_record?: string | null; issue_date?: string | null;
  expiry_date?: string | null; reminder_date?: string | null; verification_status?: string | null;
}
export interface CompanyDocument extends DocumentMetadata { id: string; label: string; filename: string | null; source_url?: string | null; version: number; reminder_status?: string | null }
export const companyLogos = {
  url: (projectId: string, companyId: string, id: string) => `/api/v1${root(projectId)}/${companyId}/logos/${id}`,
  create: async (projectId: string, companyId: string, file: File) => {
    if (!file.size || file.size > 5 * 1024 * 1024) throw new Error("Choose a logo up to 5 MB.");
    return postBinary<{ id: string }>(`${root(projectId)}/${companyId}/logos`, await file.arrayBuffer());
  },
  remove: (projectId: string, companyId: string, id: string, reason: string) => post<void>(`${root(projectId)}/${companyId}/logos/${id}/delete`, { reason }),
};
const documentsRoot = (projectId: string, companyId: string) => `${root(projectId)}/${companyId}/documents`;
export const companyDocuments = {
  list: (projectId: string, companyId: string) => get<CompanyDocument[]>(documentsRoot(projectId, companyId)),
  create: async (projectId: string, companyId: string, label: string, file: File, metadata: DocumentMetadata = {}) => {
    if (!file.size || file.size > 10 * 1024 * 1024) throw new Error("Upload a non-empty PDF up to 10 MB.");
    if (!file.name.toLowerCase().endsWith(".pdf")) throw new Error("Choose a PDF file.");
    const query = new URLSearchParams({ label: label.trim(), filename: file.name });
    for (const [key, value] of Object.entries(metadata)) if (value) query.set(key, value);
    return postBinary<CompanyDocument>(`${documentsRoot(projectId, companyId)}?${query}`, await file.arrayBuffer());
  },
  link: (projectId: string, companyId: string, label: string, source_url: string, metadata: DocumentMetadata) => post<CompanyDocument>(`${documentsRoot(projectId, companyId)}/link`, { label, source_url, ...metadata }),
  update: (projectId: string, companyId: string, row: CompanyDocument, label: string, metadata: DocumentMetadata = {}) => patch<CompanyDocument>(`${documentsRoot(projectId, companyId)}/${row.id}`, { label, ...metadata, expected_version: row.version }),
  download: (projectId: string, companyId: string, row: CompanyDocument) => download(`${documentsRoot(projectId, companyId)}/${row.id}/file`, row.filename ?? "company-document.pdf"),
  remove: (projectId: string, companyId: string, row: CompanyDocument, reason: string) => post<void>(`${documentsRoot(projectId, companyId)}/${row.id}/delete`, { reason, expected_version: row.version }),
};
