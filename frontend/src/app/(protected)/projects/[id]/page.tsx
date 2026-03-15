// Project detail route stub — navigation is handled by query param on the
// parent projects page (/projects?id=<projectId>).
//
// generateStaticParams satisfies the `output: "export"` requirement.
// dynamicParams = false ensures unmatched IDs return 404 from the static build.

export function generateStaticParams() {
  return [{ id: "_" }];
}

export const dynamicParams = false;

export default function ProjectDetailPageStub() {
  return null;
}
