import { get, patch, post } from "./client";
export interface EscalationFields { effective_date: string; escalation_percent: string; project_status: string }
export interface EscalationEntry extends EscalationFields { id: string; project_id: string; version: number }
export interface EscalationRegister { entries: EscalationEntry[]; can_manage: boolean }
const root = (projectId: string) => `/projects/${projectId}/price-escalations`;
export const escalations = {
  list: (projectId: string) => get<EscalationRegister>(root(projectId)),
  create: (projectId: string, body: EscalationFields) => post<EscalationEntry>(root(projectId), { ...body }),
  update: (projectId: string, entry: EscalationEntry, body: EscalationFields) => patch<EscalationEntry>(`${root(projectId)}/${entry.id}`, { ...body, version: entry.version }),
  remove: (projectId: string, entry: EscalationEntry, reason: string) => post<void>(`${root(projectId)}/${entry.id}/delete`, { version: entry.version, reason }),
};
