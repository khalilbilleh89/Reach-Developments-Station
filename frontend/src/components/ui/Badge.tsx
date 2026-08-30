import type { ReactNode } from "react";

export type Tone = "neutral" | "muted" | "success" | "warning" | "danger" | "info" | "accent";

/**
 * A short piece of state, coloured by what it means.
 *
 * The colour is decoration over a word that already says it, never the only
 * carrier of the meaning: nothing on this screen is understood by hue alone.
 */
export function Badge({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}
