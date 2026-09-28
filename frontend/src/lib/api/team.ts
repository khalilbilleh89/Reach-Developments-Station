import { get, patch, post } from "./client";

export type TeamKind = "operations" | "engineering";
export interface TeamFields {
  team: TeamKind;
  name: string;
  title: string | null;
  scope_of_work: string | null;
  email: string | null;
}
export interface TeamMember extends TeamFields { id: string; project_id: string; version: number }
export interface TeamDirectory { members: TeamMember[]; can_manage: boolean }
const root = (projectId: string) => `/projects/${projectId}/team`;
export const team = {
  list: (projectId: string) => get<TeamDirectory>(root(projectId)),
  create: (projectId: string, body: TeamFields) => post<TeamMember>(root(projectId), { ...body }),
  update: (projectId: string, member: TeamMember, body: TeamFields) => patch<TeamMember>(`${root(projectId)}/${member.id}`, { ...body, version: member.version }),
  remove: (projectId: string, member: TeamMember, reason: string) => post<void>(`${root(projectId)}/${member.id}/delete`, { version: member.version, reason }),
};
