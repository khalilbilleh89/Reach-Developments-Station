"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef } from "react";
import type { ReactNode } from "react";
import { Icon } from "./Icon";
import type { IconName } from "./Icon";
import { Tabs, TabPanel } from "./Tabs";
import { contextualRecordHref, recordReturn } from "@/components/shell/recordRoutes";
import type { RecordKind } from "@/components/shell/recordRoutes";

export type WorkspaceFact = { label: string; value: ReactNode; note?: ReactNode; tone?: "danger" | "muted" };
export type WorkspaceHeadline = { label: string; value: ReactNode; tone?: "danger" | "muted" };

export function useRecordTab(fallback = "overview"): [string, (tab: string) => void] {
  const params = useSearchParams(), router = useRouter();
  return [params.get("tab") ?? fallback, (tab) => { const next = new URLSearchParams(params); next.set("tab", tab); router.push(`/projects/?${next}`, { scroll: false }); }];
}

export function useRecordHref(projectId: string) {
  const params = useSearchParams();
  return (kind: RecordKind, id: string, tab?: string) => contextualRecordHref(params, projectId, kind, id, tab);
}

export function RecordLink({ projectId, kind, id, tab, children, className = "button-link" }: {
  projectId: string; kind: RecordKind; id: string; tab?: string; children: ReactNode; className?: string;
}) {
  const params = useSearchParams();
  const source = `/projects/?${params}`;
  const href = contextualRecordHref(params, projectId, kind, id, tab);
  return <Link data-record-link className={className} href={href} onClick={() => {
    if (!params.has("record") && source) {
      try { sessionStorage.setItem(`reach-register:${source}`, JSON.stringify({ href, y: window.scrollY, tables: Array.from(document.querySelectorAll<HTMLElement>(".table-scroll")).map(table => ({ label: table.getAttribute("aria-label"), x: table.scrollLeft, y: table.scrollTop })) })); } catch { /* Storage may be disabled; URL context still works. */ }
    }
  }}>{children}</Link>;
}

/** A business record owns the page. No overlay, focus trap, Close or Escape navigation. */
export function RecordWorkspace({ projectId, kind, eyebrow, icon, title, subtitle, meta, status, headline, facts, actions, tabs, activeTab, onSelectTab, children }: {
  projectId: string; kind: RecordKind; eyebrow?: string; icon?: IconName; title: string; subtitle?: ReactNode;
  meta?: ReactNode; status?: ReactNode; headline?: WorkspaceHeadline; facts?: WorkspaceFact[]; actions?: ReactNode;
  tabs?: { key: string; label: string }[]; activeTab?: string; onSelectTab?: (key: string) => void; children: ReactNode;
}) {
  const params = useSearchParams(), router = useRouter(), heading = useRef<HTMLHeadingElement>(null);
  const identity = `${kind}:${params.get("unit") ?? params.get("sale") ?? params.get("reservation") ?? params.get("plan")}`;
  const back = recordReturn(params, projectId, kind), group = `${kind} workspace sections`;
  useEffect(() => { heading.current?.focus({ preventScroll: true }); }, [identity]);
  useEffect(() => {
    if (tabs?.length && activeTab && params.get("tab") !== activeTab) {
      const next = new URLSearchParams(params); next.set("tab", activeTab);
      router.replace(`/projects/?${next}`, { scroll: false });
    }
  }, [activeTab, tabs, params, router]);
  return <article className={`record-workspace workspace-${kind}`}>
    <nav className="record-breadcrumb" aria-label="Record location">
      <Link href={back.href}>Back to {back.label}</Link>
      {back.href !== back.origin ? <><span aria-hidden="true">·</span><Link href={back.origin}>{back.originLabel} register</Link></> : null}
      <span aria-hidden="true">/</span><span>{title}</span>
    </nav>
    <header className="record-workspace-header">
      <div className="workspace-identity">{icon ? <Icon name={icon} /> : null}<div><p className="eyebrow">{eyebrow}</p><h1 ref={heading} tabIndex={-1}>{title}</h1>{subtitle ? <div className="workspace-context">{subtitle}</div> : null}</div></div>
      {headline ? <div className={`workspace-value ${headline.tone ? "workspace-value-secondary" : ""}`}><strong>{headline.value}</strong><span>{headline.label}</span></div> : null}
      {actions ? <div className="workspace-actions">{actions}</div> : null}
      {meta ? <div className="workspace-meta">{meta}</div> : null}
    </header>
    {status ? <div className="workspace-status">{status}</div> : null}
    {facts?.length ? <dl className="workspace-facts">{facts.map(fact => <div key={fact.label}><dt>{fact.label}</dt><dd>{fact.value}</dd>{fact.note ? <p>{fact.note}</p> : null}</div>)}</dl> : null}
    {tabs?.length && activeTab && onSelectTab ? <div className="workspace-tabs"><Tabs label={group} tabs={tabs} active={activeTab} onSelect={onSelectTab} variant="record" /></div> : null}
    <div className="workspace-content">{tabs?.length && activeTab ? <TabPanel group={group} tab={activeTab}>{children}</TabPanel> : children}</div>
  </article>;
}

