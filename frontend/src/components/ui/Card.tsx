import type { ReactNode } from "react";

/**
 * The one container.
 *
 * A titled region with an optional description and an optional set of actions
 * in its header. Everything on a working screen sits in one of these, so the
 * page reads as a stack of answered questions rather than a wall.
 */
export function Card({
  title,
  description,
  actions,
  headingLevel = 2,
  flush,
  children,
}: {
  title?: string;
  description?: string;
  actions?: ReactNode;
  headingLevel?: 2 | 3;
  flush?: boolean;
  children: ReactNode;
}) {
  const Heading = headingLevel === 3 ? "h3" : "h2";
  return (
    <section className="card">
      {title ? (
        <header className="card-header">
          <div className="card-header-main">
            <Heading className="card-title">{title}</Heading>
            {description ? <p className="card-description">{description}</p> : null}
          </div>
          {actions ? <div className="card-actions">{actions}</div> : null}
        </header>
      ) : null}
      <div className={flush ? "card-body card-body-flush" : "card-body"}>{children}</div>
    </section>
  );
}

/** The long-standing name for the same container. */
export const Panel = Card;

/** A bordered region inside a card: a form that opened, or a nested register. */
export function SubPanel({
  title,
  actions,
  children,
}: {
  title?: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="subpanel">
      {title || actions ? (
        <header className="subpanel-header">
          {title ? <h3 className="subpanel-title">{title}</h3> : <span />}
          {actions ? <div className="card-actions">{actions}</div> : null}
        </header>
      ) : null}
      {children}
    </section>
  );
}
