import { TenderComparisonClient } from "./TenderComparisonClient";

/**
 * Project tender comparisons route — server component entry.
 *
 * Renders the tender comparison management page for a project.
 * All interactive logic is delegated to TenderComparisonClient (client
 * component), keeping server/client module boundaries correct in App Router.
 */
export function generateStaticParams() {
  return [{ id: "_" }];
}

export const dynamicParams = false;

export default function ProjectTenderComparisonsPage() {
  return <TenderComparisonClient />;
}
