import type { ReactNode } from "react";

/** How much of the page's attention this block has earned. */
export type CardTone = "command" | "attention" | "subtle";

/**
 * The one container, in four weights.
 *
 * A titled region with an optional description and an optional set of actions
 * in its header. `tone` is hierarchy, not decoration, and a page has at most
 * one of the strong ones:
 *
 * - `command` is the answer the page exists to give — a position, a result.
 *   It carries the navigation rail's ink as a hairline, because it belongs to
 *   the same object the reader navigated with.
 * - `attention` is something owed, blocked or past its date: a narrow warm
 *   rail and the faintest tint, never a red page.
 * - `subtle` recedes — a supporting block beside something that matters more.
 * - No tone is the ordinary operational surface, and most blocks are that.
 *
 * Giving everything a tone is the same as giving nothing one.
 */
export function Card({
  title,
  description,
  actions,
  headingLevel = 2,
  flush,
  tone,
  children,
}: {
  title?: string;
  description?: string;
  actions?: ReactNode;
  headingLevel?: 2 | 3;
  flush?: boolean;
  tone?: CardTone;
  children: ReactNode;
}) {
  const Heading = headingLevel === 3 ? "h3" : "h2";
  return (
    <section className={tone ? `card card-${tone}` : "card"}>
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

/**
 * A ruled band inside a card or a record: a form that opened, a nested
 * register. A rule above and a title, never a second box inside the first —
 * box-in-box is the one composition this system refuses.
 */
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
