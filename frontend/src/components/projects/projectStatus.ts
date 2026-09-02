import type { Tone } from "@/components/ui";

/**
 * How a project's lifecycle state is written, and the colour it is drawn in.
 *
 * One place, so the portfolio, the rail and the overview never disagree about
 * what "on_hold" is called. The tone repeats what the word says; it never
 * carries the meaning on its own.
 */
const LABELS: Record<string, string> = {
  setup: "Setup",
  predevelopment: "Pre-development",
  active: "Active",
  on_hold: "On hold",
  completed: "Completed",
  cancelled: "Cancelled",
};

const TONES: Record<string, Tone> = {
  setup: "muted",
  predevelopment: "info",
  active: "success",
  on_hold: "warning",
  completed: "neutral",
  cancelled: "danger",
};

export const PROJECT_STATUSES = Object.keys(LABELS);

export function projectStatusLabel(status: string): string {
  return LABELS[status] ?? status;
}

export function projectStatusTone(status: string): Tone {
  return TONES[status] ?? "neutral";
}
