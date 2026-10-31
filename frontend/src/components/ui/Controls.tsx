"use client";

import { useId } from "react";
import type { ReactNode } from "react";

/**
 * An on/off setting, shown as the switch a phone taught everyone to read.
 * For a choice that takes effect at once (show inactive units, compact
 * rows); a choice that is saved with a form stays a checkbox.
 */
export function Switch({
  checked,
  onChange,
  children,
  disabled,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  children: ReactNode;
  disabled?: boolean;
}) {
  return (
    <label className="switch">
      <input
        type="checkbox"
        role="switch"
        className="switch-input"
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
      />
      <span className="switch-track" aria-hidden="true" />
      <span className="switch-label">{children}</span>
    </label>
  );
}

/**
 * A short definition on hover or focus, for a term whose meaning a reader
 * may not carry: "penetration", "EAC", "statutory clock". The term stays in
 * the sentence; the definition is one line and never holds a figure that is
 * not also on the page.
 */
export function Tooltip({ term, children }: { term: ReactNode; children: ReactNode }) {
  const id = useId();
  return (
    <span className="tooltip">
      <span className="tooltip-term" tabIndex={0} aria-describedby={id}>
        {term}
      </span>
      <span role="tooltip" id={id} className="tooltip-bubble">
        {children}
      </span>
    </span>
  );
}

/** Up to five people on a record, as initials; the count says the rest. */
export function AvatarStack({ people, max = 4 }: { people: { name: string }[]; max?: number }) {
  const shown = people.slice(0, max);
  const rest = people.length - shown.length;
  return (
    <span className="avatar-stack" aria-label={people.map((person) => person.name).join(", ")}>
      {shown.map((person) => (
        <span key={person.name} className="avatar" title={person.name} aria-hidden="true">
          {initials(person.name)}
        </span>
      ))}
      {rest > 0 ? (
        <span className="avatar avatar-more" aria-hidden="true">
          +{rest}
        </span>
      ) : null}
    </span>
  );
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  const first = parts[0]?.[0] ?? "";
  const last = parts.length > 1 ? parts[parts.length - 1][0] : "";
  return (first + last).toUpperCase();
}

/** A key a person can press, written as a key looks. */
export function Kbd({ children }: { children: ReactNode }) {
  return <kbd className="kbd">{children}</kbd>;
}
