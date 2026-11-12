import { get, post, put } from "./client";

export type OperationsInput = { client_id: string; beneficiary_name: string; reason: string; amount: string };
export type OperationsCommission = OperationsInput & { id: string; project_id: string; client_display: string; currency_id: string; version: number; created_at: string };
export type OperationsRegister = { items: OperationsCommission[]; clients: { id: string; display_name: string; client_number: string }[]; currency_id: string };
const root = (projectId: string) => `/projects/${projectId}/commissions/operations`;
export const operationsCommissions = {
  list: (projectId: string) => get<OperationsRegister>(root(projectId)),
  create: (projectId: string, body: OperationsInput) => post<OperationsCommission>(root(projectId), body),
  update: (projectId: string, row: OperationsCommission, body: OperationsInput) => put<OperationsCommission>(`${root(projectId)}/${row.id}`, { ...body, expected_version: row.version }),
  remove: (projectId: string, row: OperationsCommission, reason: string) => post<void>(`${root(projectId)}/${row.id}/delete`, { expected_version: row.version, reason }),
};
