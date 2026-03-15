// This dynamic route is superseded by query-param navigation on the parent page.
// Navigation: /units-pricing/[unitId] → /units-pricing?unitId=...
//
// generateStaticParams returns a placeholder so `output: "export"` is satisfied.
// No real unit IDs are pre-rendered at build time.
// dynamicParams = false ensures unmatched paths return 404 from the static export.

export function generateStaticParams() {
  return [{ unitId: "_" }];
}

export const dynamicParams = false;

export default function UnitPricingDetailPageStub() {
  return null;
}
