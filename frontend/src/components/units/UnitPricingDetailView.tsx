"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { PageContainer } from "@/components/shell/PageContainer";
import { UnitPricingSummaryCard } from "@/components/units/UnitPricingSummaryCard";
import { UnitPricingBreakdown } from "@/components/units/UnitPricingBreakdown";
import { UnitAttributesPanel } from "@/components/units/UnitAttributesPanel";
import { getUnitPricingDetail } from "@/lib/units-api";
import type { UnitPricingDetail } from "@/lib/units-types";
import styles from "@/styles/units-pricing.module.css";

/**
 * UnitPricingDetailView — full pricing inspection view for a single unit.
 *
 * Reads ?unitId= from the URL query string instead of a path param so the
 * view is compatible with Next.js static export (output: "export").
 *
 * Displays:
 *   - Pricing summary card (total price, price/sqm, area, status)
 *   - Unit attributes panel (physical + commercial attributes)
 *   - Pricing breakdown (base price, premiums, final price)
 *
 * All data is sourced from backend endpoints via getUnitPricingDetail().
 * No pricing calculations are performed on the frontend.
 *
 * Pricing readiness states:
 *   READY              — full pricing detail is shown.
 *   MISSING_ATTRIBUTES — pricing engine inputs not configured; setup prompt.
 *   MISSING_PRICING_RECORD — no pricing record exists; setup prompt.
 *   ERROR              — unexpected backend/network failure; error banner.
 */
export default function UnitPricingDetailView() {
  const searchParams = useSearchParams();
  const unitId = searchParams.get("unitId") ?? "";

  const [detail, setDetail] = useState<UnitPricingDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!unitId) {
      setLoading(false);
      setError("No unit ID provided.");
      return;
    }
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

      {/* True system error — unexpected backend/network failure */}
      {error && <div className={styles.errorState}>{error}</div>}

      {/* Pricing attributes not configured (HTTP 422 from engine) */}
      {!loading && detail && detail.pricingState === "MISSING_ATTRIBUTES" && (
        <div className={styles.setupState}>
          <h2 className={styles.setupTitle}>Pricing Not Available Yet</h2>
          <p className={styles.setupMessage}>
            Required pricing attributes are missing for this unit. Configure
            the pricing attributes before calculating a price.
          </p>
          <div className={styles.setupActions}>
            <Link
              href={`/units-pricing?unitId=${unitId}&action=editAttributes`}
              className={styles.actionBtn}
            >
              Edit Attributes
            </Link>
            <Link
              href={`/units-pricing?unitId=${unitId}&action=editPricing`}
              className={styles.actionBtn}
            >
              Edit Pricing
            </Link>
          </div>
        </div>
      )}

      {/* Pricing record not created yet (HTTP 404 from engine) */}
      {!loading && detail && detail.pricingState === "MISSING_PRICING_RECORD" && (
        <div className={styles.setupState}>
          <h2 className={styles.setupTitle}>Unit Pricing Not Configured</h2>
          <p className={styles.setupMessage}>
            No pricing record has been created for this unit yet.
          </p>
          <div className={styles.setupActions}>
            <Link
              href={`/units-pricing?unitId=${unitId}`}
              className={styles.actionBtn}
            >
              Create Pricing Record
            </Link>
          </div>
        </div>
      )}

      {/* Fully configured — show complete pricing detail */}
      {!loading && detail && detail.pricingState === "READY" && (
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
