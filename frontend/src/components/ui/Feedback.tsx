"use client";

import type { ReactNode } from "react";

import { Icon } from "./Icon";

type NoticeTone = "error" | "success" | "info" | "warning";

const NOTICE_ICON = {
  error: "alert",
  warning: "alert",
  success: "check",
  info: "info",
} as const;

/**
 * Something the system needs to say about what just happened, or about what is
 * standing in the way.
 *
 * An error is announced; everything else is a polite status update. The message
 * is the server's own words wherever there is one, because the server is the
 * only thing that knows why it refused.
 */
export function Notice({ tone, children }: { tone: NoticeTone; children: ReactNode }) {
  return (
    <div className={`notice notice-${tone}`} role={tone === "error" ? "alert" : "status"}>
      <Icon name={NOTICE_ICON[tone]} className="notice-icon" />
      <div>{children}</div>
    </div>
  );
}

/**
 * Nothing here — what is missing, why it matters, and what to do next.
 *
 * Never a placeholder figure and never an invented row. Empty space is better
 * than false information, and a hint that names the next step is better than
 * both.
 */
export function EmptyState({
  title,
  hint,
  actions,
  compact,
}: {
  title: string;
  hint?: string;
  actions?: ReactNode;
  compact?: boolean;
}) {
  return (
    <div className={compact ? "empty-state empty-state-compact" : "empty-state"}>
      <p className="empty-title">{title}</p>
      {hint ? <p className="empty-hint">{hint}</p> : null}
      {actions ? <div className="empty-actions">{actions}</div> : null}
    </div>
  );
}

/**
 * Waiting, with the shape of what is coming so the page does not jump.
 *
 * `lines` draws a paragraph's worth of placeholder; `shape` draws the
 * silhouette of a metric strip, a register, or a whole page. With neither it
 * is a short sentence.
 */
export function Loading({
  label,
  lines = 0,
  shape,
  rows = 5,
}: {
  label: string;
  lines?: number;
  shape?: "metrics" | "rows" | "page";
  rows?: number;
}) {
  if (shape === "metrics") {
    return (
      <div role="status" aria-label={label} className="skeleton-metrics">
        {Array.from({ length: 4 }, (_, index) => (
          <div key={index} className="skeleton-metric">
            <span className="skeleton" />
            <span className="skeleton" />
          </div>
        ))}
      </div>
    );
  }
  if (shape === "rows") {
    return (
      <div role="status" aria-label={label} className="skeleton-rows">
        {Array.from({ length: rows }, (_, index) => (
          <div key={index} className="skeleton-row">
            <span className="skeleton" />
            <span className="skeleton" />
            <span className="skeleton" />
            <span className="skeleton" />
          </div>
        ))}
      </div>
    );
  }
  if (shape === "page") {
    return (
      <div role="status" aria-label={label}>
        <span className="skeleton skeleton-title" />
        <div className="skeleton-lines">
          <span className="skeleton" />
          <span className="skeleton" />
          <span className="skeleton" />
        </div>
      </div>
    );
  }
  if (lines > 0) {
    return (
      <div role="status" aria-label={label}>
        <div className="skeleton-lines">
          {Array.from({ length: lines }, (_, index) => (
            <span key={index} className="skeleton" />
          ))}
        </div>
      </div>
    );
  }
  return (
    <p className="loading" role="status">
      {label}
    </p>
  );
}
