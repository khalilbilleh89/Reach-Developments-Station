"use client";

import type { ChangeEvent, FormEvent, InputHTMLAttributes, ReactNode } from "react";

import { Button } from "./Button";
import { Icon } from "./Icon";

/**
 * One labelled control.
 *
 * The label wraps the control rather than pointing at it by id, so every field
 * is clickable, nothing depends on an id staying unique across a screen that
 * renders the same form twice, and the hint and the error are read out as part
 * of the label without any wiring.
 */
export function Field({
  label,
  hint,
  error,
  optional,
  children,
  grow,
  className,
}: {
  label: string;
  hint?: string;
  error?: string | null;
  /** Say so in the label. Everything else is required, so only this is marked. */
  optional?: boolean;
  children: ReactNode;
  grow?: boolean;
  className?: string;
}) {
  const classes = ["field", grow ? "field-grow" : "", className ?? ""].filter(Boolean).join(" ");
  return (
    <label className={classes}>
      <span className="field-label">
        {label}
        {optional ? <span className="field-optional">Optional</span> : null}
      </span>
      {children}
      {error ? <span className="field-error">{error}</span> : null}
      {hint ? <span className="field-hint">{hint}</span> : null}
    </label>
  );
}

/** Fields side by side. Collapses to one column on a phone. */
export function FieldRow({
  columns = 2,
  children,
}: {
  columns?: 1 | 2 | 3 | 4;
  children: ReactNode;
}) {
  return <div className={columns === 2 ? "field-row" : `field-row field-row-${columns}`}>{children}</div>;
}

/** A titled group of related fields inside one form. */
export function FormSection({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    <div className="form-section">
      <div className="form-section-head">
        <h3 className="form-section-title">{title}</h3>
        {description ? <p className="form-section-description">{description}</p> : null}
      </div>
      {children}
    </div>
  );
}

type ShellInputProps = Omit<InputHTMLAttributes<HTMLInputElement>, "onChange" | "value"> & {
  value: string;
  onChange: (value: string) => void;
};

/**
 * Money entry: the amount, with its denomination attached.
 *
 * The value stays the exact string the person typed and the server will
 * receive; nothing here parses it into a float. The code is decoration on the
 * control — the record's own currency, resolved by the caller — and it is
 * shown as a dash where the caller genuinely cannot name one, never guessed.
 */
export function MoneyInput({ code, value, onChange, className, ...rest }: ShellInputProps & { code: string | null }) {
  return (
    <span className={className ? `input-shell input-shell-money ${className}` : "input-shell input-shell-money"}>
      <input
        className="input"
        inputMode="decimal"
        autoComplete="off"
        value={value}
        onChange={(event: ChangeEvent<HTMLInputElement>) => onChange(event.target.value)}
        {...rest}
      />
      <span className="input-affix" aria-hidden="true">
        {code ?? "—"}
      </span>
    </span>
  );
}

/**
 * A rate, entered as a percentage.
 *
 * The person types "5" or "18.5"; the caller turns it into the server's
 * fraction of one with `fractionFromPercent`, which moves the decimal point
 * by string manipulation and never multiplies. Rate and money must look
 * different, and this is what makes them different.
 */
export function RateInput({ value, onChange, className, ...rest }: ShellInputProps) {
  return (
    <span className={className ? `input-shell input-shell-rate ${className}` : "input-shell input-shell-rate"}>
      <input
        className="input"
        inputMode="decimal"
        autoComplete="off"
        value={value}
        onChange={(event: ChangeEvent<HTMLInputElement>) => onChange(event.target.value)}
        {...rest}
      />
      <span className="input-affix" aria-hidden="true">
        %
      </span>
    </span>
  );
}

/**
 * The strip above a register that narrows it.
 *
 * Search on the left, two or three filters beside it, and on the right the
 * count of what matched and the way to clear everything. Distinct from a form
 * because it records nothing: changing a filter changes what you are looking
 * at, never what is true. The module decides which filters exist; this only
 * lays them out.
 */
export function DataToolbar({
  search,
  children,
  count,
  onReset,
  actions,
  framed,
}: {
  search?: {
    value: string;
    onChange: (value: string) => void;
    placeholder?: string;
    label?: string;
  };
  children?: ReactNode;
  count?: { shown: number; total?: number; noun: string };
  onReset?: () => void;
  actions?: ReactNode;
  /**
   * Draw the row as one command surface rather than as separate controls.
   * A register's toolbar is a single instrument — search, the two or three
   * filters that narrow it, and the count of what survived — and five
   * independently bordered boxes make it read as five unrelated questions.
   */
  framed?: boolean;
}) {
  const plural = (n: number, noun: string) => `${n} ${noun}${n === 1 ? "" : "s"}`;
  return (
    <div className={framed ? "toolbar toolbar-framed" : "toolbar"} role="search">
      {search ? (
        <label className="toolbar-search">
          <span className="visually-hidden">{search.label ?? "Search"}</span>
          <Icon name="search" />
          <input
            className="input"
            type="search"
            placeholder={search.placeholder}
            value={search.value}
            onChange={(event) => search.onChange(event.target.value)}
          />
        </label>
      ) : null}
      {children}
      {count || onReset || actions ? (
        <div className="toolbar-meta">
          {count ? (
            <span className="toolbar-count" aria-live="polite">
              {count.total !== undefined && count.total !== count.shown
                ? `${count.shown} of ${plural(count.total, count.noun)}`
                : plural(count.shown, count.noun)}
            </span>
          ) : null}
          {onReset ? (
            <Button small variant="quiet" onClick={onReset}>
              Clear filters
            </Button>
          ) : null}
          {actions ? <div className="toolbar-actions">{actions}</div> : null}
        </div>
      ) : null}
    </div>
  );
}

/**
 * One filter in the toolbar. The control's first option is its visible label.
 *
 * `active` marks a filter that is currently narrowing the register, so a
 * reader who cannot find a row can see why without opening every control.
 */
export function ToolbarFilter({
  label,
  active,
  children,
}: {
  label: string;
  active?: boolean;
  children: ReactNode;
}) {
  return (
    <label className={active ? "field toolbar-filter toolbar-filter-active" : "field toolbar-filter"}>
      <span className="visually-hidden">{label}</span>
      {children}
    </label>
  );
}

/** The actions that close a form. */
export function FormActions({ children }: { children: ReactNode }) {
  return <div className="form-actions">{children}</div>;
}

/**
 * Save and cancel, pinned to the bottom of a long form.
 *
 * Used where the fields run past a screen: an operator should never have to
 * scroll to find out whether their work can be saved.
 */
export function StickyActions({
  note,
  submitLabel,
  busy,
  onCancel,
}: {
  note?: string;
  submitLabel: string;
  busy?: boolean;
  onCancel?: () => void;
}) {
  return (
    <div className="sticky-actions">
      {note ? <p className="sticky-actions-note">{note}</p> : null}
      {onCancel ? (
        <Button onClick={onCancel} disabled={busy}>
          Cancel
        </Button>
      ) : null}
      <Button variant="primary" type="submit" disabled={busy}>
        {busy ? "Saving…" : submitLabel}
      </Button>
    </div>
  );
}

/** A form that does not reload the page. */
export function Form({
  className,
  onSubmit,
  children,
}: {
  className?: string;
  onSubmit: (event: FormEvent) => void;
  children: ReactNode;
}) {
  return (
    <form className={className} onSubmit={onSubmit}>
      {children}
    </form>
  );
}
