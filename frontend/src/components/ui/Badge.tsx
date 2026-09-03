import type { ReactNode } from "react";

export type Tone = "neutral" | "muted" | "success" | "warning" | "danger" | "info" | "accent";

/**
 * A short piece of state, coloured by what it means.
 *
 * The colour is decoration over a word that already says it, never the only
 * carrier of the meaning: nothing on this screen is understood by hue alone.
 * Reserve it for the state that matters most on the row — a lifecycle state,
 * a blocker. Everything secondary is a `StatusDot` or plain text.
 */
export function Badge({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

/**
 * The lighter status treatment: a dot beside the word.
 *
 * For a secondary dimension, or a column whose heading already says it holds
 * a status, where a row of filled badges would shout. The word stays; the dot
 * is a skim aid.
 */
export function StatusDot({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
  return <span className={`status-dot status-dot-${tone}`}>{children}</span>;
}
