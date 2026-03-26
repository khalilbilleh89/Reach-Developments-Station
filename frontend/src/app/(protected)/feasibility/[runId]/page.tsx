// Feasibility run detail route — server component shell.
//
// Renders a dedicated, shareable route for a single feasibility run:
//   /feasibility/<runId>
//
// The query-param detail route (/feasibility?runId=<runId>) remains functional.
// This path-based route is the canonical deep-link entry point for direct sharing.
//
// generateStaticParams returns a placeholder so the static export build passes.
// dynamicParams = false ensures unmatched IDs return 404 from the static build.

import FeasibilityRunDeepLinkClient from "./_page-client";

export function generateStaticParams() {
  return [{ runId: "_" }];
}

export const dynamicParams = false;

export default function FeasibilityRunDetailPage({
  params,
}: {
  params: { runId: string };
}) {
  return <FeasibilityRunDeepLinkClient runId={params.runId} />;
}
