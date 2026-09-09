import { projectHref } from "./navigation";
import type { ProjectSection } from "./navigation";

export type RecordKind = "unit" | "sale" | "reservation" | "payment-plan";
export const recordModules: Record<RecordKind, ProjectSection> = { unit: "inventory", sale: "sales", reservation: "sales", "payment-plan": "payments" };
const idKeys: Record<RecordKind, string> = { unit: "unit", sale: "sale", reservation: "reservation", "payment-plan": "plan" };
export function isRecordKind(value: string | null): value is RecordKind {
  return value !== null && Object.hasOwn(recordModules, value);
}
export function readRecord(params: { get: (name: string) => string | null }) {
  const kind = params.get("record");
  if (!kind) return null;
  if (!isRecordKind(kind)) return { invalid: true } as const;
  const id = params.get(idKeys[kind]);
  if (!id || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id)) return { invalid: true } as const;
  return { invalid: false, kind, id } as const;
}
/** Runtime identifiers stay in the query of the existing static-export page. */
export function recordHref(projectId: string, kind: RecordKind, id: string, tab = "overview") {
  const params = new URLSearchParams({ project: projectId, section: recordModules[kind], record: kind, [idKeys[kind]]: id, tab });
  return `/projects/?${params}`;
}
/** A contextual return can only address this project's original module. */
export function registerReturn(value: string | null, projectId: string, section: ProjectSection) {
  if (value?.startsWith("/projects/?")) {
    const params = new URLSearchParams(value.slice(value.indexOf("?") + 1));
    if (params.get("project") === projectId && params.get("section") === section && !params.has("record")) return `/projects/?${params}`;
  }
  return projectHref(projectId, section);
}
