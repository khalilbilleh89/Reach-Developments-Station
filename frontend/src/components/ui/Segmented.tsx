import type { ReactNode } from "react";

/** Switches between presentations of the same records; the pressed segment is the one on screen. */
export function Segmented<Value extends string>({ label, value, options, onChange }: {
  label: string; value: Value; options: { value: Value; label: ReactNode }[]; onChange: (value: Value) => void;
}) {
  return <div className="segmented" role="group" aria-label={label}>
    {options.map(option => <button key={option.value} type="button" className="segment" aria-pressed={value === option.value} onClick={() => onChange(option.value)}>{option.label}</button>)}
  </div>;
}
