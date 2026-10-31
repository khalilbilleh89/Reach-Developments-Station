import type { ReactNode, Ref } from "react";
import { Icon } from "./Icon";

/**
 * Secondary evidence behind a row that opens in place (design system D3).
 *
 * The arrow sits before the label and turns to point down when the row is
 * open, as a file tree does; the old arrow at the far right of a full-width
 * row read as "something is wrong here" rather than "there is more". A short
 * `context` beside the label says what is inside before it is opened — a
 * count, the leader, a date — so a row can be left closed with confidence.
 *
 * This is for evidence a reader may want and does not need: a method, a
 * source list, a reconciliation. A breakdown a reader comes for is shown
 * open, as a `Views` toggle or tabs, never behind this.
 */
export function Disclosure({ title, context, children, open, ref, summaryRef }: {
  title: ReactNode; context?: ReactNode; children: ReactNode; open?: boolean;
  ref?: Ref<HTMLDetailsElement>; summaryRef?: Ref<HTMLElement>;
}) {
  return <details className="disclosure" open={open} ref={ref}>
    <summary className="disclosure-trigger" ref={summaryRef}>
      <Icon name="chevron" className="disclosure-chevron" />
      <span className="disclosure-label">{title}</span>
      {context ? <span className="disclosure-context">{context}</span> : null}
    </summary>
    <div className="disclosure-content">{children}</div>
  </details>;
}
