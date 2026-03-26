// Feasibility run detail route entry — server component.
//
// Navigation to a specific run is handled via query param on the parent page:
//   /feasibility?runId=<runId>
//
// This route stub satisfies Next.js `output: "export"` routing requirements.
// generateStaticParams returns a placeholder so the static export build passes.
// dynamicParams = false ensures unmatched IDs return 404 from the static build.

export function generateStaticParams() {
  return [{ runId: "_" }];
}

export const dynamicParams = false;

export default function FeasibilityRunDetailPageStub() {
  return null;
}
