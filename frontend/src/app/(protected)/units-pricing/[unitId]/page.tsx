"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { PageContainer } from "@/components/shell/PageContainer";
import { UnitPricingSummaryCard } from "@/components/units/UnitPricingSummaryCard";
import { UnitPricingBreakdown } from "@/components/units/UnitPricingBreakdown";
import { UnitAttributesPanel } from "@/components/units/UnitAttributesPanel";
import { getUnitPricingDetail } from "@/lib/units-api";
import type { UnitPricingDetail } from "@/lib/units-types";
import styles from "@/styles/units-pricing.module.css";

interface UnitPricingDetailPageProps {
  params: { unitId: string };
}

/**
 * UnitPricingDetailPage — full pricing inspection view for a single unit.
 *
 * Displays:
 *   - Pricing summary card (total price, price/sqm, area, status)
 *   - Unit attributes panel (physical + commercial attributes)
 *   - Pricing breakdown (base price, premiums, final price)
 *
 * All data is sourced from backend endpoints via getUnitPricingDetail().
 * No pricing calculations are performed on the frontend.
 */
export default function UnitPricingDetailPage({
  params,
}: UnitPricingDetailPageProps) {
  const { unitId } = params;
  const [detail, setDetail] = useState<UnitPricingDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getUnitPricingDetail(unitId)
      .then(setDetail)
      .catch((err: unknown) => {
        setError(
          err instanceof Error ? err.message : "Failed to load unit details.",
        );
      })
      .finally(() => setLoading(false));
  }, [unitId]);

  const title = detail
    ? `Unit ${detail.unit.unit_number}`
    : "Unit Pricing Detail";

  return (
    <PageContainer title={title} subtitle="Unit pricing inspection.">
      <Link href="/units-pricing" className={styles.backLink} aria-label="Back to units list">
        ← Back to Units &amp; Pricing
      </Link>

      {loading && (
        <div className={styles.loadingState}>Loading unit details…</div>
      )}

      {error && <div className={styles.errorState}>{error}</div>}

      {detail && (
        <div className={styles.detailLayout}>
          {/* Pricing summary — full width */}
          <div className={styles.detailFullWidth}>
            <UnitPricingSummaryCard
              unit={detail.unit}
              pricing={detail.pricing}
            />
          </div>

          {/* Unit attributes */}
          <UnitAttributesPanel unit={detail.unit} />

          {/* Pricing breakdown */}
          <UnitPricingBreakdown
            pricing={detail.pricing}
            attributes={detail.attributes}
          />
        </div>
      )}
    </PageContainer>
  );
}
