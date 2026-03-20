// Project structure route — static export stub.
//
// The actual structure UI (Buildings → Floors → Units hierarchy) is rendered
// by the projects page via query params
// (/projects?id=<projectId>&tab=buildings or &tab=floors).
//
// generateStaticParams satisfies the `output: "export"` requirement.
// dynamicParams = false ensures unmatched IDs return 404 from the static build.

export function generateStaticParams() {
  return [{ id: "_" }];
}

export const dynamicParams = false;

export default function ProjectStructurePageStub() {
  return null;
}
