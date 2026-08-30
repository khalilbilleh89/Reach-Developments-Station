/**
 * How payment plan vocabulary is written for people.
 *
 * One place, so a version never reads "Awaiting sanction" in the register and
 * "submitted" in the panel beneath it. An unknown value falls through
 * unchanged: a status the interface has not been taught is still a status
 * somebody needs to see.
 *
 * The trigger wording is chosen with some care. An instalment waiting on a
 * construction milestone is "Awaiting certification", never "Due soon" — the
 * whole point of PR-MVP-06 is that a forecast date does not make money due, and
 * the words on screen must not undo what the schema enforces.
 */

import type { Tone } from "@/components/ui";

const VERSION_LABELS: Record<string, string> = {
  draft: "Draft",
  submitted: "Awaiting approval",
  approved: "Approved",
  active: "Active",
  superseded: "Superseded",
  rejected: "Refused",
};

const TRIGGER_LABELS: Record<string, string> = {
  fixed_date: "Fixed date",
  days_after_spa: "Days after SPA",
  recurring_monthly: "Monthly",
  recurring_quarterly: "Quarterly",
  construction_milestone: "Construction milestone",
  handover: "Handover",
  title_transfer: "Title transfer",
  manual_approved_event: "Approved event",
};

const TRIGGER_STATUS_LABELS: Record<string, string> = {
  scheduled: "Scheduled",
  awaiting_trigger: "Awaiting trigger",
  triggered: "Triggered",
};

const ALLOCATION_LABELS: Record<string, string> = {
  percentage: "By percentage",
  amount: "By amount",
};

const CHARGE_LABELS: Record<string, string> = {
  pro_rata: "Spread pro rata",
  manual: "Entered per instalment",
};

const RESERVATION_LABELS: Record<string, string> = {
  included_in_schedule: "Shown in the schedule",
  reference_only: "Held on the deal",
};

const ORIGIN_LABELS: Record<string, string> = {
  custom: "Built for this sale",
  copied_plan: "Copied from an approved plan",
};

const EVENT_LABELS: Record<string, string> = {
  submitted: "Awaiting approval",
  approved: "Approved",
  reversed: "Withdrawn",
};

function lookup(table: Record<string, string>, value: string | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return table[value] ?? value;
}

export const versionLabel = (value: string | null | undefined) => lookup(VERSION_LABELS, value);
export const triggerLabel = (value: string | null | undefined) => lookup(TRIGGER_LABELS, value);
export const triggerStatusLabel = (value: string | null | undefined) =>
  lookup(TRIGGER_STATUS_LABELS, value);
export const allocationLabel = (value: string | null | undefined) =>
  lookup(ALLOCATION_LABELS, value);
export const chargeLabel = (value: string | null | undefined) => lookup(CHARGE_LABELS, value);
export const reservationTreatmentLabel = (value: string | null | undefined) =>
  lookup(RESERVATION_LABELS, value);
export const originLabel = (value: string | null | undefined) => lookup(ORIGIN_LABELS, value);
export const triggerEventLabel = (value: string | null | undefined) => lookup(EVENT_LABELS, value);

/**
 * The colour each word is drawn in.
 *
 * Presentation over a word that already says it. An instalment awaiting a
 * trigger is drawn neutral rather than as a warning: waiting for a milestone
 * is the ordinary state of a milestone instalment, not a problem.
 */
function toner(table: Record<string, Tone>) {
  return (value: string | null | undefined): Tone =>
    value === null || value === undefined ? "muted" : (table[value] ?? "neutral");
}

export const versionTone = toner({
  draft: "muted",
  submitted: "warning",
  approved: "info",
  active: "success",
  superseded: "neutral",
  rejected: "danger",
});

export const triggerStatusTone = toner({
  scheduled: "info",
  awaiting_trigger: "neutral",
  triggered: "success",
});

export const triggerEventTone = toner({
  submitted: "warning",
  approved: "success",
  reversed: "muted",
});

/** The trigger types a preparer may choose, in the order they are offered. */
export const TRIGGER_TYPES = Object.keys(TRIGGER_LABELS);

/** Triggers whose due date the calendar settles when the plan is written. */
export const DATE_BASED_TRIGGERS = new Set([
  "fixed_date",
  "days_after_spa",
  "recurring_monthly",
  "recurring_quarterly",
]);

/** Triggers that need a reference naming the thing being waited on. */
export const REFERENCE_TRIGGERS = new Set(["construction_milestone", "manual_approved_event"]);

/** The lifecycle a version passes, for the steps strip. */
export const VERSION_SEQUENCE = ["draft", "submitted", "approved", "active"];
