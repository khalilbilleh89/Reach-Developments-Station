import { get, post, patch } from "./client";

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
}
export interface BankAccount extends BankFields { id: string }
export interface Company extends CompanyFields { id: string; bank_accounts: BankAccount[] }

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

