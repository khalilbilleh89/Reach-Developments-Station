import type { ReactNode } from "react";

import type { RecordPageFact } from "./RecordPage";

/**
 * The figures a record is opened for, in one strip under its head (design
 * system K4): the one that matters on a gold panel, the others beside it.
 * Every value is the server's, formatted; nothing is derived here.
 */
export function RecordStrip({ lead, items }: { lead: RecordPageFact; items: RecordPageFact[] }) {
  return (
    <dl className="record-strip">
      <div className={lead.tone ? `record-strip-lead record-strip-${lead.tone}` : "record-strip-lead"}>
        <dt>{lead.label}</dt>
        <dd>{lead.value}</dd>
        {lead.note ? <p>{lead.note}</p> : null}
      </div>
      {items.filter((item) => item.value !== null && item.value !== undefined).map((item) => (
        <div key={item.label} className={item.tone ? `record-strip-item record-strip-${item.tone}` : "record-strip-item"}>
          <dt>{item.label}</dt>
          <dd>{item.value}</dd>
          {item.note ? <p>{item.note}</p> : null}
        </div>
      ))}
    </dl>
  );
}

/**
 * What the record needs next, in one line with the one action that does it
 * (design system K4). It states the server's own position — an overdue
 * instalment, a missing requirement, the stage a deal has reached — and
 * never a judgement the browser formed.
 */
export function NextBar({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className="next-bar" role="status">
      <span className="next-bar-text"><strong>Next</strong> {children}</span>
      {action ? <span className="next-bar-action">{action}</span> : null}
    </div>
  );
}
