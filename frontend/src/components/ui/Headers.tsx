import type { ReactNode } from "react";

/**
 * The top of a page: where you are, what it is for, where it stands, and what
 * you can do here.
 *
 * Title and one sentence of purpose on the left, with the page's current
 * state beside the title where a page has one; the page's actions on the
 * right, the primary one obvious and everything else quiet; and beneath the
 * title, the small facts that identify the place — a code, a currency, a date.
 * Not figures: figures are labelled and belong in a `Position` beneath.
 *
 * `compact` trims the vertical space for register-heavy pages, where every
 * row of the table is worth more than a row of chrome.
 */
export function PageHeader({
  eyebrow,
  title,
  subtitle,
  status,
  actions,
  meta,
  compact,
}: {
  eyebrow?: string;
  title: string;
  subtitle?: string;
  /** The page's current state, drawn beside the title: a badge, a dot. */
  status?: ReactNode;
  actions?: ReactNode;
  meta?: ReactNode;
  compact?: boolean;
}) {
  return (
    <header className={compact ? "page-head page-head-compact" : "page-head"}>
      <div className="page-head-main">
        {eyebrow ? <p className="page-eyebrow">{eyebrow}</p> : null}
        {status ? (
          <div className="page-title-row">
            <h1 className="page-title">{title}</h1>
            {status}
          </div>
        ) : (
          <h1 className="page-title">{title}</h1>
        )}
        {subtitle ? <p className="page-subtitle">{subtitle}</p> : null}
        {meta ? <div className="page-meta">{meta}</div> : null}
      </div>
      {actions ? <div className="page-actions">{actions}</div> : null}
    </header>
  );
}

/** A labelled division inside a card or a record, with room for one action beside it. */
export function SectionHeader({
  title,
  description,
  actions,
  id,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
  id?: string;
}) {
  return (
    <>
      <div className="section-header">
        <h3 className="section-heading" id={id}>
          {title}
        </h3>
        {actions ? <div className="card-actions">{actions}</div> : null}
      </div>
      {description ? <p className="section-description">{description}</p> : null}
    </>
  );
}
