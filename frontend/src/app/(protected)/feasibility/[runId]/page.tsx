/**
 * Feasibility Run Detail page — server component shell.
 *
 * Exports generateStaticParams and dynamicParams for Next.js output: "export"
 * compatibility, then delegates all interactive rendering to the client component.
 *
 * generateStaticParams returns a placeholder so the static build does not error.
 * Client-side navigation within the app resolves the real runId via useParams().
 *
 * PR-W5.2
 */

import { FeasibilityRunDetailClient } from "./_page-client";

export function generateStaticParams() {
  return [{ runId: "_" }];
}

export const dynamicParams = false;

export default function FeasibilityRunDetailPage() {
  return <FeasibilityRunDetailClient />;
}
