// Feasibility run detail route stub — navigation is handled by query param on the
// parent feasibility page (/feasibility?runId=<runId>).
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
