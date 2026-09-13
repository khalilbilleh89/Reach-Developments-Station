import type { ConsultantWorkspace, PermitRegister } from "@/lib/api";
export type BriefingDate = { id: string; date: string; title: string; context: string; section: "permits" | "consultant" };
/** Recorded open targets, not inferred completion or calculated project health. */
export function briefingDates(permits: PermitRegister | null, design: ConsultantWorkspace | null): BriefingDate[] {
  const dates: BriefingDate[] = [];
  for (const permit of permits?.permits ?? []) {
    if (permit.planned_issue_date && !["issued", "completed", "renewed", "withdrawn", "rejected", "expired"].includes(permit.status)) {
      dates.push({id: "permit:" + permit.id, date: permit.planned_issue_date, title: permit.permit_code, context: "Permit · required by", section: "permits"});
    }
  }
  const engagement = design?.active_engagement?.id;
  if (engagement) {
    for (const stage of design?.stages ?? []) {
      const date = stage.forecast_date ?? stage.planned_date;
      if (stage.engagement_id === engagement && date && !["completed", "cancelled"].includes(stage.status)) dates.push({id:"stage:" + stage.id,date,title:stage.name,context:stage.forecast_date ? "Design stage · forecast" : "Design stage · planned",section:"consultant"});
    }
    for (const item of design?.deliverables ?? []) {
      if (item.engagement_id === engagement && item.due_date && !["accepted", "superseded", "cancelled"].includes(item.status)) dates.push({id:"deliverable:" + item.id,date:item.due_date,title:item.name,context:"Deliverable · due",section:"consultant"});
    }
  }
  return dates.sort((a,b)=>a.date.localeCompare(b.date) || a.id.localeCompare(b.id));
}
