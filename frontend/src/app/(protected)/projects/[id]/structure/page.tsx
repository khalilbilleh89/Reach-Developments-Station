import { ProjectStructureClient } from "./ProjectStructureClient";

/**
 * Project structure viewer route — server component entry.
 *
 * Renders the full canonical hierarchy for a project:
 *   Project → Phase → Building → Floor → Unit
 *
 * All interactive rendering is delegated to ProjectStructureClient (client
 * component), keeping server/client module boundaries correct in App Router.
 *
 * generateStaticParams and dynamicParams satisfy the Next.js `output: "export"`
 * requirement, consistent with all other dynamic route entries.
 */
export function generateStaticParams() {
  return [{ id: "_" }];
}

export const dynamicParams = false;

export default function ProjectStructurePage() {
  return <ProjectStructureClient />;
}

