import { get, patch, post } from "./client";

export interface Stage {
  id: string; name: string; sequence: number; planned_date: string | null;
}
export interface UnitStage extends Stage {
  completed_date: string | null; revision: number; status: "complete" | "pending";
  history: { completed_date: string | null; reason: string; actor_user_id: string;
    recorded_at: string; sequence: number }[];
}
export interface UnitProgress {
  unit_id: string; delivery_status: string; completed_count: number;
  stage_count: number; stages: UnitStage[];
}
const root = (projectId: string) => `/projects/${projectId}/construction`;
export const stages = {
  list: (projectId: string) => get<Stage[]>(`${root(projectId)}/stages`),
  update: (projectId: string, stage: Stage, changes: {
    name?: string; planned_date?: string | null; sequence?: number; expected_order?: string[];
  }) => patch<Stage>(`${root(projectId)}/stages/${stage.id}`, {
    expected_name: stage.name, expected_planned_date: stage.planned_date,
    expected_sequence: stage.sequence, ...changes,
  }),
  create: (projectId: string, name: string, plannedDate: string | null) =>
    post<Stage>(`${root(projectId)}/stages`, { name, planned_date: plannedDate }),
  unit: (projectId: string, unitId: string) =>
    get<UnitProgress>(`${root(projectId)}/units/${unitId}/stages`),
  complete: (projectId: string, unitId: string, stage: UnitStage,
    completedDate: string | null, reason: string) =>
    post<void>(`${root(projectId)}/units/${unitId}/stages/${stage.id}/completion`, {
      completed_date: completedDate, reason, expected_revision: stage.revision,
    }),
};
