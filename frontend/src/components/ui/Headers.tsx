import type { ReactNode } from "react";

/**
 * The top of a page: where you are, what it is, and what you can do here.
 *
 * `meta` is for the small facts that identify the record — a code, a country, a
 * currency — not for figures. Figures belong in a `Stat`, where they are
 * labelled.
 */
export function PageHeader({
  eyebrow,
  title,
  subtitle,
  actions,
  meta,
}: {
  eyebrow?: string;
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  meta?: ReactNode;
}) {
  return (
    <header>
      <div className="page-header">
        <div className="page-header-main">
          {eyebrow ? <p className="page-eyebrow">{eyebrow}</p> : null}
          <h1 className="page-title">{title}</h1>
          {subtitle ? <p className="page-subtitle">{subtitle}</p> : null}
        </div>
        {actions ? <div className="page-actions">{actions}</div> : null}
      </div>
      {meta ? <div className="page-meta">{meta}</div> : null}
    </header>
  );
}

/** A labelled division inside a card, with room for one action beside it. */
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
