import { contextualRecordHref } from "@/components/shell/recordRoutes";

/** Successful preparation returns to the register, never an empty creation form. */
export function createdSalesHref(query: {toString: () => string}, projectId: string, kind: "reservation" | "sale", id: string) {
  const origin = new URLSearchParams(query.toString());
  origin.delete("sales_view");
  return contextualRecordHref(origin, projectId, kind, id);
}
