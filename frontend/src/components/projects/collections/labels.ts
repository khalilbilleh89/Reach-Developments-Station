/**
 * How collections vocabulary is written for people.
 *
 * One place, so a receipt never reads "Awaiting confirmation" in the register
 * and "recorded" in the panel beneath it. An unknown value falls through
 * unchanged: a status the interface has not been taught is still a status
 * somebody needs to see.
 *
 * Two choices of wording are deliberate rather than cosmetic.
 *
 * A recorded receipt is **"Awaiting confirmation"**, never "Received". It has
 * not moved a balance and the words must not suggest it has — a collections
 * officer reading "Received" beside an unchanged outstanding figure will
 * conclude the screen is broken, and be half right.
 *
 * A waiver is **"Collection paused"**, never "Balance waived". The obligation
 * is untouched by anything in this module, and language that implies otherwise
 * would undo in the interface exactly what the schema is enforcing.
 */

import type { Tone } from "@/components/ui";

const RECEIPT_LABELS: Record<string, string> = {
  recorded: "Awaiting confirmation",
  confirmed: "Confirmed",
  reversed: "Reversed",
};

const ALLOCATION_LABELS: Record<string, string> = {
  active: "Applied",
  superseded: "Carried forward",
  reversed: "Reversed",
};

const INSTALLMENT_LABELS: Record<string, string> = {
  awaiting_trigger: "Awaiting trigger",
  scheduled: "Scheduled",
  due: "Due",
  partially_paid: "Part paid",
  paid: "Paid",
  overdue: "Overdue",
  disputed: "Disputed",
  cancelled: "Cancelled",
};

const UNIT_COLLECTION_LABELS: Record<string, string> = {
  not_started: "Not started",
  current: "Current",
  partially_paid: "Part paid",
  overdue: "Overdue",
  disputed: "Disputed",
  cleared: "Cleared",
  cancelled: "Cancelled",
};

const BUCKET_LABELS: Record<string, string> = {
  awaiting_trigger: "Awaiting trigger",
  current: "Current",
  "1_30": "1–30 days",
  "31_60": "31–60 days",
  "61_90": "61–90 days",
  "91_plus": "91+ days",
};

const ACTION_LABELS: Record<string, string> = {
  call: "Call",
  email: "Email",
  meeting: "Meeting",
  reminder: "Reminder",
  formal_notice: "Formal notice",
  promise_to_pay: "Promise to pay",
  legal_referral: "Legal referral",
  follow_up: "Follow-up",
  other: "Other",
};

const DISPUTE_LABELS: Record<string, string> = {
  open: "Open",
  resolved: "Resolved",
  withdrawn: "Withdrawn",
};

const WAIVER_TYPE_LABELS: Record<string, string> = {
  collection_hold: "Collection hold",
  grace_extension: "Grace extension",
};

const WAIVER_LABELS: Record<string, string> = {
  submitted: "Awaiting approval",
  approved: "Collection paused",
  rejected: "Refused",
  revoked: "Withdrawn",
};

const RESTRUCTURE_LABELS: Record<string, string> = {
  open: "In progress",
  applied: "Applied",
  abandoned: "Abandoned",
};

const REFUND_LABELS: Record<string, string> = {
  recorded: "Awaiting confirmation",
  confirmed: "Paid",
  reversed: "Reversed",
};

const CLEARANCE_LABELS: Record<string, string> = {
  pending: "Not given",
  cleared: "Cleared",
  revoked: "Withdrawn",
};

function lookup(table: Record<string, string>, value: string | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  return table[value] ?? value;
}

export const receiptLabel = (value: string | null | undefined) => lookup(RECEIPT_LABELS, value);
export const allocationStatusLabel = (value: string | null | undefined) =>
  lookup(ALLOCATION_LABELS, value);
export const installmentLabel = (value: string | null | undefined) =>
  lookup(INSTALLMENT_LABELS, value);
export const unitCollectionLabel = (value: string | null | undefined) =>
  lookup(UNIT_COLLECTION_LABELS, value);
export const bucketLabel = (value: string | null | undefined) => lookup(BUCKET_LABELS, value);
export const actionLabel = (value: string | null | undefined) => lookup(ACTION_LABELS, value);
export const disputeLabel = (value: string | null | undefined) => lookup(DISPUTE_LABELS, value);
export const waiverTypeLabel = (value: string | null | undefined) =>
  lookup(WAIVER_TYPE_LABELS, value);
export const waiverLabel = (value: string | null | undefined) => lookup(WAIVER_LABELS, value);
export const restructureLabel = (value: string | null | undefined) =>
  lookup(RESTRUCTURE_LABELS, value);
export const refundLabel = (value: string | null | undefined) => lookup(REFUND_LABELS, value);
export const clearanceLabel = (value: string | null | undefined) =>
  lookup(CLEARANCE_LABELS, value);

function toner(table: Record<string, Tone>) {
  return (value: string | null | undefined): Tone =>
    value ? (table[value] ?? "neutral") : "neutral";
}

/** Awaiting confirmation is `info`, not `success`: it is not money yet. */
export const receiptTone = toner({
  recorded: "info",
  confirmed: "success",
  reversed: "danger",
});

export const allocationTone = toner({
  active: "success",
  superseded: "muted",
  reversed: "danger",
});

export const installmentTone = toner({
  awaiting_trigger: "muted",
  scheduled: "neutral",
  due: "info",
  partially_paid: "warning",
  paid: "success",
  overdue: "danger",
  disputed: "danger",
  cancelled: "muted",
});

export const unitCollectionTone = toner({
  not_started: "muted",
  current: "info",
  partially_paid: "warning",
  overdue: "danger",
  disputed: "danger",
  cleared: "success",
  cancelled: "muted",
});

export const bucketTone = toner({
  awaiting_trigger: "muted",
  current: "success",
  "1_30": "warning",
  "31_60": "warning",
  "61_90": "danger",
  "91_plus": "danger",
});

export const waiverTone = toner({
  submitted: "info",
  approved: "warning",
  rejected: "muted",
  revoked: "muted",
});

export const disputeTone = toner({
  open: "danger",
  resolved: "success",
  withdrawn: "muted",
});

export const restructureTone = toner({
  open: "info",
  applied: "success",
  abandoned: "muted",
});

export const refundTone = toner({
  recorded: "info",
  confirmed: "success",
  reversed: "danger",
});

export const clearanceTone = toner({
  pending: "warning",
  cleared: "success",
  revoked: "danger",
});

/** The bands, in report order. */
export const AGING_BUCKETS = [
  "current",
  "1_30",
  "31_60",
  "61_90",
  "91_plus",
  "awaiting_trigger",
] as const;

export const ACTION_TYPES = Object.keys(ACTION_LABELS);
export const WAIVER_TYPES = Object.keys(WAIVER_TYPE_LABELS);
