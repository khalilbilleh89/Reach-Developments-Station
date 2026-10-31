"use client";

import { useEffect, useId, useRef, useState } from "react";
import type { ReactNode } from "react";

import { Icon } from "./Icon";

export type Coverage = "available" | "partial" | "unavailable";

/**
 * Where a figure came from and how it was worked out, behind one small
 * control beside the figure's title (design system C1/C2/C4).
 *
 * The old "Available · 63 records in sample · Method ⌄" line stood under
 * every analysis section and read as noise; it is replaced by an info mark
 * (C1) that opens the sample size, coverage and method on click. With
 * `chip`, the sample size shows in the mark itself (C2), and a partial
 * coverage draws a four-bar meter in the chip (C4). Nothing is hidden that
 * was shown before: the words move into the popover.
 */
export function SourceNote({
  coverage,
  sampleSize,
  sampleNoun = "records",
  reason,
  method,
  chip,
  label = "How this is calculated",
}: {
  coverage: Coverage;
  sampleSize: number;
  sampleNoun?: string;
  /** Why coverage is partial or unavailable; shown first when it is. */
  reason?: string | null;
  /** The server's statement of the basis. */
  method: ReactNode;
  /** Show the sample size in the control (C2) instead of a bare mark (C1). */
  chip?: boolean;
  label?: string;
}) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const root = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    if (!open) return;
    const outside = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", outside);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("pointerdown", outside);
      document.removeEventListener("keydown", escape);
    };
  }, [open]);

  const coverageText =
    coverage === "available" ? "Complete" : coverage === "partial" ? "Partial coverage" : "Unavailable";
  const bars = coverage === "available" ? 4 : coverage === "partial" ? 2 : 0;

  return (
    <span className="source-note" ref={root}>
      <button
        type="button"
        className={chip ? "source-note-chip" : "source-note-mark"}
        aria-label={chip ? undefined : label}
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen((value) => !value)}
      >
        {chip ? (
          <>
            {coverage === "available" ? (
              <span className={`source-note-dot source-note-dot-${coverage}`} aria-hidden="true" />
            ) : (
              <span className="source-note-meter" aria-hidden="true">
                {[0, 1, 2, 3].map((index) => (
                  <i key={index} className={index < bars ? "on" : undefined} />
                ))}
              </span>
            )}
            <span>
              {sampleSize} {sampleNoun}
            </span>
          </>
        ) : (
          <Icon name="info" />
        )}
      </button>
      <span className="source-note-pop" id={id} role="note" hidden={!open}>
        <strong>
          {sampleSize} {sampleNoun} · {coverageText}
        </strong>
        {coverage !== "available" && reason ? <span className="source-note-reason">{reason}</span> : null}
        <span className="source-note-method">{method}</span>
      </span>
    </span>
  );
}
