import { findNavItem, isProjectSection, PROJECT_NAVIGATION, projectHref } from "./navigation";
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
/** Context is local to one project. Never accept an external or nested return URL. */
function contextParams(value: string | null, projectId: string) {
  if (!value?.startsWith("/projects/?") || value.length > 4096 || value.includes("#")) return null;
  const params = new URLSearchParams(value.slice(value.indexOf("?") + 1));
  if (params.get("project") !== projectId || !isProjectSection(params.get("section") ?? "overview")) return null;
  params.delete("return");
  params.delete("trail");
  return params;
}

/** The origin may be any valid register in this project, including another module. */
export function registerReturn(value: string | null, projectId: string, section: ProjectSection) {
  const params = contextParams(value, projectId);
  if (params && !params.has("record")) return `/projects/?${params}`;
  return projectHref(projectId, section);
}

type Query = { get: (key: string) => string | null; toString: () => string };
const recordLabels: Record<RecordKind, string> = { unit: "Unit", sale: "Sale", reservation: "Reservation", "payment-plan": "Payment Plan" };

// A flat, bounded trail avoids recursively encoding return URLs. Revisited records
// unwind to their original position; long journeys retain their eight nearest parents.
function recordTrail(params: Query, projectId: string): string[] {
  const raw = params.get("trail");
  if (!raw || raw.length > 8192) return [];
  try {
    const values: unknown = JSON.parse(raw);
    if (!Array.isArray(values) || values.length > 8) return [];
    const trail: string[] = [];
    for (const value of values) {
      const item = contextParams(typeof value === "string" ? value : null, projectId);
      const record = item && readRecord(item);
      if (!item || !record || record.invalid || item.get("section") !== recordModules[record.kind]) return [];
      trail.push(recordHref(projectId, record.kind, record.id, item.get("tab") ?? "overview"));
    }
    return trail;
  } catch { return []; }
}

function withContext(href: string, origin: string, trail: string[]) {
  return `${href}&return=${encodeURIComponent(origin)}${trail.length ? `&trail=${encodeURIComponent(JSON.stringify(trail))}` : ""}`;
}

/** Shared by ordinary links and post-create navigation. Works without browser history/storage. */
export function contextualRecordHref(params: Query, projectId: string, kind: RecordKind, id: string, tab = "overview") {
  const source = contextParams(`/projects/?${params}`, projectId);
  const current = source && readRecord(source);
  const origin = registerReturn(current ? params.get("return") : source ? `/projects/?${source}` : null, projectId, current && !current.invalid ? recordModules[current.kind] : recordModules[kind]);
  let trail = source ? recordTrail(params, projectId) : [];
  if (current && !current.invalid) {
    trail.push(recordHref(projectId, current.kind, current.id, source!.get("tab") ?? "overview"));
  }
  const previous = trail.findIndex(value => {
    const record = readRecord(new URLSearchParams(value.split("?")[1]));
    return record && !record.invalid && record.kind === kind && record.id === id;
  });
  if (previous >= 0) trail = trail.slice(0, previous);
  return withContext(recordHref(projectId, kind, id, tab), origin, trail.slice(-8));
}

export function recordReturn(params: Query, projectId: string, kind: RecordKind) {
  const origin = registerReturn(params.get("return"), projectId, recordModules[kind]);
  const section = new URLSearchParams(origin.split("?")[1]).get("section") ?? "overview";
  const originLabel = findNavItem(PROJECT_NAVIGATION, section)?.label ?? "Overview";
  const trail = recordTrail(params, projectId);
  // Reject self-return links in hand-edited or stale addresses.
  const current = readRecord(params);
  while (trail.length) {
    const parent = trail.pop()!;
    const record = readRecord(new URLSearchParams(parent.split("?")[1]));
    if (record && !record.invalid && !(current && !current.invalid && record.kind === current.kind && record.id === current.id)) {
      return { origin, originLabel, href: withContext(parent, origin, trail), label: recordLabels[record.kind] };
    }
  }
  return { origin, originLabel, href: origin, label: originLabel };
}
