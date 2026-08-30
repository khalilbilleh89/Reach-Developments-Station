"use client";

import { useEffect, useRef } from "react";
import type { ReactNode } from "react";

import { Button } from "./Button";
import { TabPanel, Tabs } from "./Tabs";

/**
 * A record opened over the register that led to it.
 *
 * Escape closes it, clicking the scrim closes it, and the page behind stops
 * scrolling while it is open so a phone does not quietly move the list out from
 * under the person's thumb. Focus moves in on open and the drawer is labelled,
 * so a screen reader announces which record was opened rather than reading the
 * register again.
 */
export function Drawer({
  eyebrow,
  title,
  subtitle,
  meta,
  tabs,
  activeTab,
  onSelectTab,
  onClose,
  children,
}: {
  eyebrow?: string;
  title: string;
  subtitle?: string;
  meta?: ReactNode;
  tabs?: { key: string; label: string }[];
  activeTab?: string;
  onSelectTab?: (key: string) => void;
  onClose: () => void;
  children: ReactNode;
}) {
  const panel = useRef<HTMLDivElement>(null);

  useEffect(() => {
    panel.current?.focus();
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", escape);
    return () => {
      document.body.style.overflow = previous;
      document.removeEventListener("keydown", escape);
    };
  }, [onClose]);

  return (
    <div
      className="drawer-scrim"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        className="drawer"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        ref={panel}
      >
        <header className="drawer-header">
          <div className="drawer-title-row">
            <div>
              {eyebrow ? <p className="drawer-eyebrow">{eyebrow}</p> : null}
              <h2 className="drawer-title">{title}</h2>
              {subtitle ? <p className="drawer-subtitle">{subtitle}</p> : null}
            </div>
            <Button onClick={onClose}>Close</Button>
          </div>
          {meta ? <div className="drawer-meta">{meta}</div> : null}
          {tabs && activeTab && onSelectTab ? (
            <Tabs label="Record sections" tabs={tabs} active={activeTab} onSelect={onSelectTab} />
          ) : (
            <div className="drawer-header-pad" />
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
