// Feasibility run detail route stub used to satisfy Next.js routing and static export.
// This route is currently a no-op; run details are not rendered via this page.
//
// generateStaticParams satisfies the `output: "export"` requirement.
// dynamicParams = false ensures unmatched IDs return 404 from the static build.

export function generateStaticParams() {
  return [{ runId: "_" }];
}

export const dynamicParams = false;

export default function FeasibilityRunDetailPageStub() {
  return null;
}
