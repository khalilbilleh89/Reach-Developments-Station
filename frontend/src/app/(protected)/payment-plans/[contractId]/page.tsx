// This dynamic route is superseded by query-param navigation on the parent page.
// Navigation: /payment-plans/[contractId] → /payment-plans?contractId=...
//
// generateStaticParams returns a placeholder so `output: "export"` is satisfied.
// No real contract IDs are pre-rendered at build time.
// dynamicParams = false ensures unmatched paths return 404 from the static export.

export function generateStaticParams() {
  return [{ contractId: "_" }];
}

export const dynamicParams = false;

export default function PaymentPlanDetailPageStub() {
  return null;
}
