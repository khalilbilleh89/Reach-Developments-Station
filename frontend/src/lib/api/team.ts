import { download, get, patch, post, postBinary } from "./client";

export type TeamKind = "operations" | "engineering";
export interface TeamFields {
  team: TeamKind;
  name: string;
  title: string | null;
  scope_of_work: string | null;
  email: string | null;
}
export interface TeamMember extends TeamFields { id: string; project_id: string; version: number; job_description: { id: string; filename: string } | null }
export interface TeamDirectory { members: TeamMember[]; can_manage: boolean }
const root = (projectId: string) => `/projects/${projectId}/team`;
export const team = {
  uploadDocument: async (projectId: string, member: TeamMember, file: File) => {
    if (!file.size || file.size > 10 * 1024 * 1024) throw new Error("Upload a non-empty PDF or Word document up to 10 MB.");
    const query = new URLSearchParams({ filename: file.name, version: String(member.version) });
    return postBinary<TeamMember>(`${root(projectId)}/${member.id}/job-description?${query}`, await file.arrayBuffer());
  },
  downloadDocument: (projectId: string, member: TeamMember) => download(`${root(projectId)}/${member.id}/job-description`, member.job_description?.filename ?? "job-description"),
  removeDocument: (projectId: string, member: TeamMember, reason: string) => post<void>(`${root(projectId)}/${member.id}/job-description/delete`, { version: member.version, reason }),
  list: (projectId: string) => get<TeamDirectory>(root(projectId)),
  create: (projectId: string, body: TeamFields) => post<TeamMember>(root(projectId), { ...body }),
  update: (projectId: string, member: TeamMember, body: TeamFields) => patch<TeamMember>(`${root(projectId)}/${member.id}`, { ...body, version: member.version }),
  remove: (projectId: string, member: TeamMember, reason: string) => post<void>(`${root(projectId)}/${member.id}/delete`, { version: member.version, reason }),
};
