import type { ReactNode } from "react";

import { Icon } from "./Icon";

/**
 * A condition a person must deal with before carrying on, pinned above the
 * content it concerns: unsaved changes, a forecast taken before movements
 * were confirmed, a permit blocking the programme. It stays until acted on;
 * it is never a confirmation (that is a toast) and never a failed request
 * (that is a notice beside what failed).
 */
export function Banner({
  tone = "warning",
  children,
  action,
}: {
  tone?: "warning" | "info" | "danger";
  children: ReactNode;
  /** The one control that resolves the condition. */
  action?: ReactNode;
}) {
  return (
    <div className={`banner banner-${tone}`} role={tone === "danger" ? "alert" : "status"}>
      <Icon name={tone === "info" ? "info" : "alert"} className="banner-icon" />
      <div className="banner-text">{children}</div>
      {action ? <div className="banner-action">{action}</div> : null}
    </div>
  );
}
