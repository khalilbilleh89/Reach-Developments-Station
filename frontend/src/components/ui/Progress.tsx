import type { ReactNode } from "react";

/**
 * How far along a staged thing is, one segment per stage, the current stage
 * on gold (design system H3c). `done` and `total` are the server's counts;
 * the bar draws exactly that many segments and reads them out.
 */
export function StageBar({ label, done, total, note }: { label: string; done: number; total: number; note?: ReactNode }) {
  const segments = Math.max(0, Math.min(total, 60));
  return (
    <div className="stage-bar">
      <span className="stage-bar-label">{label}</span>
      <span className="stage-bar-segments" role="img" aria-label={`${label}: ${done} of ${total} stages complete`}>
        {Array.from({ length: segments }, (_, index) => (
          <i key={index} className={index < done ? "stage-bar-done" : index === done && done < total ? "stage-bar-current" : undefined} />
        ))}
      </span>
      <span className="stage-bar-value">{done} / {total}</span>
      {note ? <span className="stage-bar-note">{note}</span> : null}
    </div>
  );
}

/**
 * A single reported percentage as a ring (design system H3c), with the one
 * in focus on gold. The percentage is the server's; the ring's arc is only
 * its geometry.
 */
export function ProgressRing({ percent, label, note, focus }: { percent: number | string; label: string; note?: ReactNode; focus?: boolean }) {
  const value = Math.max(0, Math.min(100, Number(percent)));
  const radius = 26;
  const circumference = 2 * Math.PI * radius;
  return (
    <div className={focus ? "ring ring-focus" : "ring"}>
      <svg className="ring-svg" viewBox="0 0 64 64" width="64" height="64" role="img" aria-label={`${label}: ${percent}%`}>
        <circle className="ring-track" cx="32" cy="32" r={radius} />
        <circle className="ring-arc" cx="32" cy="32" r={radius} strokeDasharray={`${circumference}`} strokeDashoffset={`${circumference * (1 - value / 100)}`} />
        <text className="ring-text" x="32" y="32" textAnchor="middle" dominantBaseline="central">{percent}%</text>
      </svg>
      <span className="ring-text-block">
        <span className="ring-label">{label}</span>
        {note ? <span className="ring-note">{note}</span> : null}
      </span>
    </div>
  );
}
