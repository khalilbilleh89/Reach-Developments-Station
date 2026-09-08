import type { ReactNode } from "react";
import { Icon } from "./Icon";

/** Secondary evidence with native keyboard/expanded semantics and a consistent hit target. */
export function Disclosure({ title, context, children, open }: {
  title: string; context?: ReactNode; children: ReactNode; open?: boolean;
}) {
  return <details className="disclosure" open={open}>
    <summary className="disclosure-trigger">
      <span className="disclosure-label">{title}</span>
      {context ? <span className="disclosure-context">{context}</span> : null}
      <Icon name="chevron-down" className="disclosure-chevron" />
    </summary>
    <div className="disclosure-content">{children}</div>
  </details>;
}
