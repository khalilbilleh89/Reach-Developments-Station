// The Buildings → Floors → Units structure UI is currently rendered
// inside the main Projects page through the ProjectDetailView tabbed
// interface. Those tabs are controlled by React component state rather
// than URL query parameters.
//
// This route exists only to satisfy Next.js static export requirements
// (`output: "export"`) for the dynamic segment `/projects/[id]/structure`.
//
// It also acts as a placeholder for potential future nested routing
// where the structure view could be separated into its own page.
//
// generateStaticParams ensures the static build knows which routes exist.
// dynamicParams = false ensures unknown IDs return a static 404.

export function generateStaticParams() {
  return [{ id: "_" }];
}

export const dynamicParams = false;

export default function ProjectStructurePageStub() {
  return null;
}
