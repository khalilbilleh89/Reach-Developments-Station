import type { ReactNode } from "react";

export type TimelineState = "done" | "current" | "void" | "pending";

/**
 * What happened to a record, in the order it happened.
 *
 * Every entry is an event the server recorded. Nothing is inferred: a milestone
 * that has not been reported simply is not here, and one that was withdrawn is
 * shown struck through rather than deleted, because it did happen.
 */
export function Timeline({ children }: { children: ReactNode }) {
  return <ol className="timeline">{children}</ol>;
}

export function TimelineItem({
  title,
  date,
  state = "done",
  detail,
  aside,
}: {
  title: string;
  date?: string | null;
  state?: TimelineState;
  detail?: ReactNode;
  aside?: ReactNode;
}) {
  return (
    <li className={`timeline-item timeline-item-${state}`}>
      <div className="timeline-head">
        <span className={state === "void" ? "timeline-title timeline-title-void" : "timeline-title"}>
          {title}
        </span>
        {date ? <span className="timeline-date">{date}</span> : null}
        {aside}
      </div>
      {detail ? <div className="timeline-detail">{detail}</div> : null}
    </li>
  );
}

/**
 * The named steps a record passes, with the one it has reached marked.
 *
 * The server decides which step that is; this only draws it.
 */
export function Steps({
  label,
  steps,
}: {
  label: string;
  steps: { key: string; label: string; state: "done" | "current" | "pending" }[];
}) {
  return (
    <ol className="steps" aria-label={label}>
      {steps.map((step) => (
        <li
          key={step.key}
          className={step.state === "pending" ? "step" : `step step-${step.state}`}
          aria-current={step.state === "current" ? "step" : undefined}
        >
          {step.label}
        </li>
      ))}
    </ol>
  );
}
