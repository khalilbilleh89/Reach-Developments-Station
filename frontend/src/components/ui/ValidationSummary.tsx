"use client";
import { useEffect, useId, useRef } from "react";
import { ApiError } from "@/lib/api";
import { Notice } from "./Feedback";

const labels: Record<string, string> = {
  client_id: "Buyer", display_name: "Buyer name", expires_on: "Reservation expires",
  price_locked_until: "Price locked until", deposit_required_amount: "Deposit required",
  sales_channel_code: "Sales channel", sales_branch_code: "Sales branch", owner_user_id: "Owner",
  due_date: "Due date", installments: "Instalment", principal_fraction: "Share",
  contractual_due_date: "Due date", fee_amount: "Buyer fee", offset_days: "Days after the SPA",
};
/** Keep structured server paths and identify both the field and its schedule row. */
export function ValidationSummary({ error }: { error: string | ApiError | null }) {
  const root = useRef<HTMLDivElement>(null);
  const id = useId();
  const fields = error instanceof ApiError ? error.fieldErrors : [];
  useEffect(() => {
    if (!error) return;
    const fields = error instanceof ApiError ? error.fieldErrors : [];
    const scope = root.current?.closest("form,[data-draft-boundary]");
    const controls = fields.map(field => scope?.querySelector<HTMLElement>(`[name="${CSS.escape(field.path.join("."))}"]`)).filter((control): control is HTMLElement => Boolean(control));
    const previous = controls.map(control => [control, control.getAttribute("aria-invalid"), control.getAttribute("aria-describedby")] as const);
    controls.forEach(control => { control.setAttribute("aria-invalid", "true"); control.setAttribute("aria-describedby", [control.getAttribute("aria-describedby"), id].filter(Boolean).join(" ")); });
    (controls[0] ?? root.current)?.focus();
    return () => previous.forEach(([control, invalid, described]) => {
      if (invalid === null) control.removeAttribute("aria-invalid"); else control.setAttribute("aria-invalid", invalid);
      if (described === null) control.removeAttribute("aria-describedby"); else control.setAttribute("aria-describedby", described);
    });
  }, [error, id]);
  if (!error) return null;
  return <div ref={root} id={id} tabIndex={-1}><Notice tone="error">{fields.length ? <>Check the following fields:<ul>{fields.map((field, index) => <li key={index}><button type="button" className="button-link" onClick={() => root.current?.closest("form,[data-draft-boundary]")?.querySelector<HTMLElement>(`[name="${CSS.escape(field.path.join("."))}"]`)?.focus()}>{field.path.map(part => typeof part === "number" ? `row ${part + 1}` : labels[part] ?? part.replaceAll("_", " ")).join(" · ")}: {field.message}</button></li>)}</ul></> : error instanceof Error ? error.message : error}</Notice></div>;
}
