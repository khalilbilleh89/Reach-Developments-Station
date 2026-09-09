import type { ReactNode } from "react";
import { Badge } from "./Badge";
import type { Tone } from "./Badge";

/** A reported exception and a route to its owner. No scoring or action workflow. */
export interface AttentionEntry {
  key: string;
  title: string;
  reason: string;
  tone: Tone;
  count?: number;
  severity?: string;
  category?: string;
  context?: ReactNode;
  evidence?: ReactNode;
  source?: ReactNode;
  action: ReactNode;
}

/** One exception composition for portfolio risks and project source counts. */
export function AttentionList({ items, detailed }: { items: AttentionEntry[]; detailed?: boolean }) {
  return <ul className={detailed ? "attention-list attention-list-detailed" : "attention-list"}>
    {items.map((item) => <li key={item.key} className="attention-item">
      <div className="attention-marker">
        {item.severity ? <Badge tone={item.tone}>{item.severity}</Badge> : null}
        {item.count !== undefined ? <span className={item.tone === "danger" ? "attention-count attention-count-danger" : item.tone === "warning" ? "attention-count attention-count-warning" : "attention-count"}>{item.count}</span> : null}
      </div>
      <div className="attention-text">
        {item.context ? <div className="attention-context">{item.context}</div> : null}
        {item.category ? <p className="attention-category">{item.category}</p> : null}
        <p className="attention-title">{item.title}</p>
        <p className="attention-hint">{item.reason}</p>
        {item.evidence ? <div className="attention-evidence">{item.evidence}</div> : null}
        {item.source ? <div className="attention-source">{item.source}</div> : null}
      </div>
      <div className="attention-action">{item.action}</div>
    </li>)}
  </ul>;
}
