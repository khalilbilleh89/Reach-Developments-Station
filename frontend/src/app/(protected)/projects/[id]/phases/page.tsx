// Project lifecycle phases route — static export stub.
//
// The actual lifecycle UI is rendered by the projects page via query params
// (/projects?id=<projectId>&tab=lifecycle).
//
// generateStaticParams satisfies the `output: "export"` requirement.
// dynamicParams = false ensures unmatched IDs return 404 from the static build.

export function generateStaticParams() {
  return [{ id: "_" }];
}

export const dynamicParams = false;

export default function ProjectPhasesPageStub() {
  return null;
}
