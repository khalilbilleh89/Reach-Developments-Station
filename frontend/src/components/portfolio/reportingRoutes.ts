export function reportingHref(id: string, view = "position", prior = "", context?: { get: (key: string) => string | null }) {
  const params = new URLSearchParams({ section: "reporting", snapshot: id, view });
  if (prior) params.set("prior", prior);
  for (const key of ["scope", "project", "offset"]) { const value = context?.get(key); if (value) params.set(key, value); }
  if (!id) { params.delete("snapshot"); params.delete("view"); params.delete("prior"); }
  return `/portfolio/?${params}`;
}
