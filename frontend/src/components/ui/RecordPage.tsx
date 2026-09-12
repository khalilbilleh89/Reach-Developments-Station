"use client";

import { createContext, useContext, useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import type { ReactNode } from "react";

import { Icon } from "./Icon";
import type { IconName } from "./Icon";
import { TabPanel, Tabs } from "./Tabs";
import { requestFormLeave } from "./UnsavedChangesGuard";

/** One supporting fact about the record: an area, a balance, a date. */
export interface RecordPageFact {
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
export interface RecordPageHeadline {
  value: ReactNode;
  label: string;
  tone?: "danger" | "muted";
}

/** The shell provides a normal document-flow destination for record pages. */
export const RecordPageHost = createContext<HTMLElement | null>(null);

/** Full-width record content replaces the register while preserving its state. */
export function RecordPage({
  eyebrow,
  icon,
  title,
  subtitle,
  meta,
  status,
  headline,
  facts,
  actions,
  tabs,
  activeTab,
  onSelectTab,
  onClose,
  children,
}: {
  eyebrow?: string;
  icon?: IconName;
  title: string;
  subtitle?: ReactNode;
  meta?: ReactNode;
  /** Independent record states, between identity and supporting facts. */
  status?: ReactNode;
  headline?: RecordPageHeadline;
  facts?: RecordPageFact[];
  /** Contextual actions beside Close: the one or two things this record invites. */
  actions?: ReactNode;
  tabs?: { key: string; label: string }[];
  activeTab?: string;
  onSelectTab?: (key: string) => void;
  onClose: () => void;
  children: ReactNode;
}) {
  const host = useContext(RecordPageHost);
  const panel = useRef<HTMLDivElement>(null);
  function close() { requestFormLeave(panel.current, onClose); }

  useEffect(() => {
    if (!host || !panel.current) return;
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const scroll = window.scrollY;
    panel.current.focus({ preventScroll: true });
    window.scrollTo({ top: 0, behavior: "instant" });
    return () => {
      requestAnimationFrame(() => {
        if (opener?.isConnected) opener.focus({ preventScroll: true });
        window.scrollTo({ top: scroll, behavior: "instant" });
      });
    };
  }, [host]);

  if (!host) return null;
  const shownFacts = (facts ?? []).filter(fact => fact.value !== null && fact.value !== undefined);
  return createPortal(
      <div
        className="record-page"
        role="region"
        aria-label={title}
        tabIndex={-1}
        ref={panel}
      >
        <header className="record-page-head">
          <div className="record-page-head-top">
            <button
              type="button"
              className="button record-page-back"
              aria-label="Back to the register"
              onClick={close}
            >
              <Icon name="arrow-left" /> Back
            </button>
            {icon ? <span className="record-glyph"><Icon name={icon} /></span> : null}
            <div className="record-page-identity">
              {eyebrow ? <p className="record-page-eyebrow">{eyebrow}</p> : null}
              <h1 className="record-page-title">{title}</h1>
              {subtitle ? <p className="record-page-subtitle">{subtitle}</p> : null}
              {meta ? <div className="record-page-meta">{meta}</div> : null}
            </div>
            {headline ? (
              <div className={headline.tone ? `record-page-headline record-page-headline-${headline.tone}` : "record-page-headline"}>
                <p className="record-page-headline-value">{headline.value}</p>
                <p className="record-page-headline-label">{headline.label}</p>
              </div>
            ) : null}
            <div className="record-page-head-actions">
              {actions}

            </div>
          </div>
          {status ? <div className="record-page-state">{status}</div> : null}
          {shownFacts.length > 0 ? (
            <dl className="record-page-facts">
              {shownFacts.map((fact) => (
                <div key={fact.label} className={fact.tone ? `record-page-fact-${fact.tone}` : undefined}>
                  <dt className="record-page-fact-label">{fact.label}</dt>
                  <dd className="record-page-fact-value">{fact.value}</dd>
                  {fact.note ? <dd className="record-page-fact-note">{fact.note}</dd> : null}
                </div>
              ))}
            </dl>
          ) : null}
          {tabs && activeTab && onSelectTab ? (
            <div className="record-page-sections">
              <Tabs variant="record" label="Record sections" tabs={tabs} active={activeTab} onSelect={onSelectTab} />
            </div>
          ) : (
            <div className="record-page-head-pad" />
          )}
        </header>
        {tabs && activeTab ? (
          <TabPanel group="Record sections" tab={activeTab} className="record-page-body stack">
            {children}
          </TabPanel>
        ) : (
          <div className="record-page-body stack">{children}</div>
        )}
      </div>,
    host,
  );
}
