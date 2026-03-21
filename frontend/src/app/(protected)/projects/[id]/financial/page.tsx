import { ProjectFinancialDashboardClient } from "./ProjectFinancialDashboardClient";

/**
 * Project financial dashboard route entry — server component.
 *
 * generateStaticParams and dynamicParams satisfy the Next.js `output: "export"`
 * requirement, consistent with all other dynamic route entries in this project.
 *
 * All interactive UI is delegated to ProjectFinancialDashboardClient (client
 * component), keeping server/client module boundaries correct in the App Router.
 */
export function generateStaticParams() {
  return [{ id: "_" }];
}

export const dynamicParams = false;

export default function ProjectFinancialPage() {
  return <ProjectFinancialDashboardClient />;
}
