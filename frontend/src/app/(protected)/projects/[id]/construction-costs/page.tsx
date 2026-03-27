import { ConstructionCostsClient } from "./ConstructionCostsClient";

/**
 * Project construction cost records route — server component entry.
 *
 * Renders the construction cost record management page for a project.
 * All interactive logic is delegated to ConstructionCostsClient (client
 * component), keeping server/client module boundaries correct in App Router.
 *
 * generateStaticParams and dynamicParams satisfy the Next.js `output: "export"`
 * requirement, consistent with all other dynamic route entries.
 */
export function generateStaticParams() {
  return [{ id: "_" }];
}

export const dynamicParams = false;

export default function ProjectConstructionCostsPage() {
  return <ConstructionCostsClient />;
}
