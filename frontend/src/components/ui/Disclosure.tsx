import type { ReactNode, Ref } from "react";
import { Icon } from "./Icon";

/** Secondary evidence with native keyboard/expanded semantics and a consistent hit target. */
export function Disclosure({ title, context, children, open, ref, summaryRef }: {
  title: ReactNode; context?: ReactNode; children: ReactNode; open?: boolean;
  ref?: Ref<HTMLDetailsElement>; summaryRef?: Ref<HTMLElement>;
}) {
  return <details className="disclosure" open={open} ref={ref}>
    <summary className="disclosure-trigger" ref={summaryRef}>
      <span className="disclosure-label">{title}</span>
      {context ? <span className="disclosure-context">{context}</span> : null}
      <Icon name="chevron-down" className="disclosure-chevron" />
    </summary>
    <div className="disclosure-content">{children}</div>
  </details>;
}
