import type { Permit } from "@/lib/api";

/** Display-only record review prompts. Never infer or change workflow status. */
export function permitReviewNotes(permit: Pick<Permit, "status" | "issue_date" | "expiry_date">): string[] {
  const notes: string[] = [];
  if (permit.status === "not_started" && permit.issue_date) {
    notes.push("An issue date is recorded while status is Not started. Confirm the status from the permit evidence.");
  }
  if (permit.issue_date && permit.expiry_date && permit.expiry_date < permit.issue_date) {
    notes.push("The recorded expiry date precedes the issue date. Review both dates against the permit evidence.");
  }
  return notes;
}
/** Current workflow family only; earlier steps are not asserted complete. */
export function permitJourneyPosition(status: string): number | null {
  if (["not_started", "preparing"].includes(status)) return 0;
  if (["submitted", "accepted_for_review", "comments_received", "resubmission"].includes(status)) return 1;
  if (["approved_with_conditions", "rejected"].includes(status)) return 2;
  if (["issued", "completed", "renewed"].includes(status)) return 3;
  return null;
}
