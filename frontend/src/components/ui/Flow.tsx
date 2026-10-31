"use client";

import type { ReactNode } from "react";

import { Button } from "./Button";

export interface FlowStep {
  key: string;
  label: string;
  /** One line under the label: what this step asks for. */
  hint?: string;
}

/**
 * The steps of a multi-step action, with the current one on a gold panel
 * (design system J4, H3c). Done steps are ticked; the ones ahead are quiet.
 * It says where the person is; it is not a navigation — the actions below
 * the step's fields move it.
 */
export function FlowSteps({ label, steps, current }: { label: string; steps: FlowStep[]; current: number }) {
  return (
    <ol className="flow-steps" aria-label={label}>
      {steps.map((step, index) => {
        const state = index < current ? "done" : index === current ? "current" : "pending";
        return (
          <li key={step.key} className={`flow-step flow-step-${state}`} aria-current={state === "current" ? "step" : undefined}>
            <span className="flow-step-mark" aria-hidden="true">{state === "done" ? "✓" : index + 1}</span>
            <span className="flow-step-text">
              <span className="flow-step-label">{step.label}</span>
              {step.hint ? <span className="flow-step-hint">{step.hint}</span> : null}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

/**
 * Back, Cancel and Next under a step; on the last step, the one submit.
 * Next is a plain button so Enter in a field never skips a step; the form's
 * own submit handler decides what Enter does.
 */
export function FlowActions({ step, count, busy, nextDisabled, submitLabel, onBack, onNext, onCancel, children }: {
  step: number;
  count: number;
  busy?: boolean;
  nextDisabled?: boolean;
  submitLabel: string;
  onBack: () => void;
  onNext: () => void;
  onCancel?: () => void;
  /** Anything else that belongs beside the actions, such as a note. */
  children?: ReactNode;
}) {
  const last = step >= count - 1;
  return (
    <div className="flow-actions">
      {children ? <div className="flow-actions-note">{children}</div> : null}
      {onCancel ? <Button data-leaves-editor disabled={busy} onClick={onCancel}>Cancel</Button> : null}
      {step > 0 ? <Button disabled={busy} onClick={onBack}>Back</Button> : null}
      {/* Keyed apart on purpose: React would otherwise keep one <button> node and
          turn Next into the submit while its click is still being dispatched, and
          the browser's default action would then submit the form. */}
      {last
        ? <Button key="submit" variant="primary" type="submit" disabled={busy || nextDisabled}>{busy ? "Saving…" : submitLabel}</Button>
        : <Button key="next" variant="primary" disabled={busy || nextDisabled} onClick={onNext}>Next</Button>}
    </div>
  );
}
