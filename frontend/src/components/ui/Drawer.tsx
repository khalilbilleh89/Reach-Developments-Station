"use client";

import { useEffect } from "react";
import type { ReactNode } from "react";

import { Button } from "./Button";
import { Icon } from "./Icon";
import { useOverlay } from "./overlay";
import { TabPanel, Tabs } from "./Tabs";

/** One supporting fact about the record: an area, a balance, a date. */
export interface DrawerFact {
  label: string;
  value: ReactNode;
  note?: ReactNode;
  /** `danger` for a figure the server flagged; `muted` for one it could not give. */
  tone?: "danger" | "muted";
}

/**
 * The one value a record is about — a unit's price, an account's balance —
 * set large beside the identity, with its basis in words beneath.
 *
 * Present only when the reader's role may see it. A role that is refused the
 * figure never has it fetched, so there is nothing here to hide.
 */
export interface DrawerHeadline {
  value: ReactNode;
  label: string;
  tone?: "danger" | "muted";
}

/**
 * A record file, opened over the register that led to it.
 *
 * Opening a record should feel like opening a file, not a modal full of
 * forms. The header is the record's identity and stays put: what it is,
 * where it sits, the state it is in, the one value it is about, the action it
 * invites, the three or four supporting figures somebody opened it to read,
 * and the sections beneath. The body scrolls under it. On a phone it takes the
 * whole screen and the way back is at the top left, where a thumb expects it.
 *
 * Modal behaviour — Escape on the topmost overlay only, focus contained while
 * open and returned to the opening control on close — comes from `useOverlay`,
 * shared with the dialogs so a reason dialog inside a drawer nests correctly:
 * the first Escape closes the dialog, the second the drawer, never both. The
 * page behind stops scrolling while the drawer is open so a phone does not
 * quietly move the list out from under the person's thumb.
 */
export function Drawer({
  eyebrow,
  title,
  subtitle,
  meta,
  headline,
  facts,
  actions,
  tabs,
  activeTab,
  onSelectTab,
  onClose,
  narrow,
  children,
}: {
  eyebrow?: string;
  title: string;
  subtitle?: ReactNode;
  meta?: ReactNode;
  headline?: DrawerHeadline;
  facts?: DrawerFact[];
  /** Contextual actions beside Close: the one or two things this record invites. */
  actions?: ReactNode;
  tabs?: { key: string; label: string }[];
  activeTab?: string;
  onSelectTab?: (key: string) => void;
  onClose: () => void;
  narrow?: boolean;
  children: ReactNode;
}) {
  const panel = useOverlay<HTMLDivElement>(onClose, "container");

  useEffect(() => {
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, []);

  const shownFacts = (facts ?? []).filter((fact) => fact.value !== null && fact.value !== undefined);

  return (
    <div
      className="drawer-scrim"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        className={narrow ? "drawer drawer-narrow" : "drawer"}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        ref={panel}
      >
        <header className="drawer-head">
          <div className="drawer-head-top">
            <button
              type="button"
              className="icon-button drawer-back"
              aria-label="Back to the register"
              onClick={onClose}
            >
              <Icon name="arrow-left" />
            </button>
            <div className="drawer-identity">
              {eyebrow ? <p className="drawer-eyebrow">{eyebrow}</p> : null}
              <h2 className="drawer-title">{title}</h2>
              {subtitle ? <p className="drawer-subtitle">{subtitle}</p> : null}
              {meta ? <div className="drawer-meta">{meta}</div> : null}
            </div>
            {headline ? (
              <div className={headline.tone ? `drawer-headline drawer-headline-${headline.tone}` : "drawer-headline"}>
                <p className="drawer-headline-value">{headline.value}</p>
                <p className="drawer-headline-label">{headline.label}</p>
              </div>
            ) : null}
            <div className="drawer-head-actions">
              {actions}
              <Button className="drawer-close-desktop" onClick={onClose}>
                Close
              </Button>
            </div>
          </div>
          {shownFacts.length > 0 ? (
            <dl className="drawer-facts">
              {shownFacts.map((fact) => (
                <div key={fact.label} className={fact.tone ? `drawer-fact-${fact.tone}` : undefined}>
                  <dt className="drawer-fact-label">{fact.label}</dt>
                  <dd className="drawer-fact-value">{fact.value}</dd>
                  {fact.note ? <dd className="drawer-fact-note">{fact.note}</dd> : null}
                </div>
              ))}
            </dl>
          ) : null}
          {tabs && activeTab && onSelectTab ? (
            <div className="drawer-sections">
              <Tabs label="Record sections" tabs={tabs} active={activeTab} onSelect={onSelectTab} />
            </div>
          ) : (
            <div className="drawer-head-pad" />
          )}
        </header>
        {tabs && activeTab ? (
          <TabPanel group="Record sections" tab={activeTab} className="drawer-body stack">
            {children}
          </TabPanel>
        ) : (
          <div className="drawer-body stack">{children}</div>
        )}
      </div>
    </div>
  );
}
