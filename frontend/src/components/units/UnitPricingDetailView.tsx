"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { PageContainer } from "@/components/shell/PageContainer";
import { UnitPricingSummaryCard } from "@/components/units/UnitPricingSummaryCard";
import { UnitPricingBreakdown } from "@/components/units/UnitPricingBreakdown";
import { UnitAttributesPanel } from "@/components/units/UnitAttributesPanel";
import { getUnitPricingDetail } from "@/lib/units-api";
import type { UnitPricingDetail, UnitQualitativeAttributes, UnitPricingRecord, UnitPricingAttributes } from "@/lib/units-types";
import { formatCurrency } from "@/lib/format-utils";
import styles from "@/styles/units-pricing.module.css";

/**
 * UnitPricingDetailView — three-layer pricing inspection view for a single unit.
 *
 * Reads ?unitId= from the URL query string instead of a path param so the
 * view is compatible with Next.js static export (output: "export").
 *
 * The three-layer pricing model:
 *
 *   Layer 1 — Qualitative Attributes (view type, corner unit, orientation, etc.)
 *     Managed via: Edit Attributes
 *     These describe the unit categorically; they do NOT block price calculation.
 *
 *   Layer 2 — Pricing Engine Inputs (base_price_per_sqm, floor_premium, etc.)
 *     Managed via: Edit Engine Inputs
 *     These are the numerical inputs consumed by the pricing engine.
 *     When any are missing, the readiness section shows which fields to fill.
 *
 *   Layer 3 — Commercial Pricing Record (approved price, status, notes)
 *     Managed via: Pricing Record / Edit Pricing Record
 *     This is the formal stored commercial price used for sales workflows.
 *
 * Pricing readiness states:
 *   READY              — full pricing detail is shown.
 *   MISSING_ATTRIBUTES — engine inputs not configured; setup prompt shown.
 *   MISSING_PRICING_RECORD — no pricing record; setup prompt shown.
 *   Unexpected failures — thrown to the error state (error banner).
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

      {/* Pricing engine inputs not configured (HTTP 422 from engine) */}
      {!loading && detail && detail.pricingState === "MISSING_ATTRIBUTES" && (
        <>
          <div className={styles.setupState}>
            <h2 className={styles.setupTitle}>Pricing Not Available Yet</h2>
            {detail.readiness && detail.readiness.missing_required_fields.length > 0 ? (
              <>
                <p className={styles.setupMessage}>
                  The following required pricing engine inputs are not yet configured
                  for this unit:
                </p>
                <ul className={styles.missingFieldsList}>
                  {detail.readiness.missing_required_fields.map((field) => (
                    <li key={field} className={styles.missingFieldsItem}>
                      {field.replace(/_/g, " ")}
                    </li>
                  ))}
                </ul>
                <p className={styles.setupMessage}>
                  Use <strong>Edit Engine Inputs</strong> to set the numerical pricing
                  engine inputs (base price per sqm, premiums, adjustments).
                  The <strong>Edit Attributes</strong> action manages qualitative
                  characteristics (view type, orientation, etc.) which do not
                  block price calculation.
                </p>
              </>
            ) : (
              <p className={styles.setupMessage}>
                Required pricing attributes are missing for this unit. Configure
                the pricing engine inputs before calculating a price.
              </p>
            )}
            <div className={styles.setupActions}>
              <Link
                href={`/units-pricing?action=editAttributes&target=${unitId}`}
                className={styles.actionBtn}
              >
                Edit Attributes
              </Link>
              <Link
                href={`/units-pricing?action=editEngineInputs&target=${unitId}`}
                className={styles.actionBtn}
              >
                Edit Engine Inputs
              </Link>
            </div>
          </div>

          {/* Layer 1 — qualitative attributes (always shown when available) */}
          {detail.qualitativeAttributes && (
            <QualitativeAttributesSection
              attrs={detail.qualitativeAttributes}
              unitId={unitId}
            />
          )}
        </>
      )}

      {/* Pricing record not created yet (HTTP 404 from engine) */}
      {!loading && detail && detail.pricingState === "MISSING_PRICING_RECORD" && (
        <>
          <div className={styles.setupState}>
            <h2 className={styles.setupTitle}>Unit Pricing Not Configured</h2>
            <p className={styles.setupMessage}>
              No pricing record has been created for this unit yet.
            </p>
            <div className={styles.setupActions}>
              <Link
                href={`/units-pricing?action=editPricing&target=${unitId}`}
                className={styles.actionBtn}
              >
                Create Pricing Record
              </Link>
            </div>
          </div>

          {/* Layer 1 — qualitative attributes */}
          {detail.qualitativeAttributes && (
            <QualitativeAttributesSection
              attrs={detail.qualitativeAttributes}
              unitId={unitId}
            />
          )}

          {/* Layer 2 — engine inputs if they exist */}
          {detail.attributes && (
            <EngineInputsSection attrs={detail.attributes} unitId={unitId} />
          )}
        </>
      )}

      {/* Fully configured — show complete three-layer pricing detail */}
      {!loading && detail && detail.pricingState === "READY" && (
        <div className={styles.detailLayout}>
          {/* Pricing summary — full width */}
          <div className={styles.detailFullWidth}>
            <UnitPricingSummaryCard
              unit={detail.unit}
              pricing={detail.pricing}
            />
          </div>

          {/* Unit physical attributes */}
          <UnitAttributesPanel unit={detail.unit} />

          {/* Pricing breakdown (engine calculation) */}
          <UnitPricingBreakdown
            pricing={detail.pricing}
            attributes={detail.attributes}
          />

          {/* Layer 1 — Qualitative Attributes */}
          {detail.qualitativeAttributes && (
            <div className={styles.detailFullWidth}>
              <QualitativeAttributesSection
                attrs={detail.qualitativeAttributes}
                unitId={unitId}
              />
            </div>
          )}

          {/* Layer 2 — Pricing Engine Inputs */}
          {detail.attributes && (
            <div className={styles.detailFullWidth}>
              <EngineInputsSection attrs={detail.attributes} unitId={unitId} />
            </div>
          )}

          {/* Layer 3 — Commercial Pricing Record */}
          {detail.pricingRecord && (
            <div className={styles.detailFullWidth}>
              <PricingRecordSection
                record={detail.pricingRecord}
                unitId={unitId}
              />
            </div>
          )}
        </div>
      )}
    </PageContainer>
  );
}

// ---------------------------------------------------------------------------
// Layer 1 — Qualitative Attributes section
// ---------------------------------------------------------------------------

function QualitativeAttributesSection({
  attrs,
  unitId,
}: {
  attrs: UnitQualitativeAttributes;
  unitId: string;
}) {
  return (
    <div className={styles.pricingSection}>
      <div className={styles.pricingSectionHeader}>
        <h3 className={styles.pricingSectionTitle}>
          Qualitative Attributes
          <span className={styles.pricingSectionBadge}>Layer 1</span>
        </h3>
        <Link
          href={`/units-pricing?action=editAttributes&target=${unitId}`}
          className={styles.sectionEditLink}
        >
          Edit Attributes
        </Link>
      </div>
      <p className={styles.pricingSectionSubtitle}>
        Descriptive / categorical inputs. These do not block price calculation.
      </p>
      <dl className={styles.pricingSectionGrid}>
        <AttributeRow label="View Type" value={attrs.view_type} />
        <AttributeRow
          label="Corner Unit"
          value={attrs.corner_unit != null ? (attrs.corner_unit ? "Yes" : "No") : null}
        />
        <AttributeRow label="Floor Category" value={attrs.floor_premium_category} />
        <AttributeRow label="Orientation" value={attrs.orientation} />
        <AttributeRow label="Outdoor Premium Type" value={attrs.outdoor_area_premium} />
        <AttributeRow
          label="Upgrade Flag"
          value={attrs.upgrade_flag != null ? (attrs.upgrade_flag ? "Yes" : "No") : null}
        />
        {attrs.notes && <AttributeRow label="Notes" value={attrs.notes} />}
      </dl>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Layer 2 — Pricing Engine Inputs section
// ---------------------------------------------------------------------------

function EngineInputsSection({
  attrs,
  unitId,
}: {
  attrs: UnitPricingAttributes;
  unitId: string;
}) {
  return (
    <div className={styles.pricingSection}>
      <div className={styles.pricingSectionHeader}>
        <h3 className={styles.pricingSectionTitle}>
          Pricing Engine Inputs
          <span className={styles.pricingSectionBadge}>Layer 2</span>
        </h3>
        <Link
          href={`/units-pricing?action=editEngineInputs&target=${unitId}`}
          className={styles.sectionEditLink}
        >
          Edit Engine Inputs
        </Link>
      </div>
      <p className={styles.pricingSectionSubtitle}>
        Numerical inputs consumed by the pricing engine. All fields must be set for readiness.
      </p>
      <dl className={styles.pricingSectionGrid}>
        <AttributeRow
          label="Base Price Per Sqm"
          value={attrs.base_price_per_sqm != null ? formatCurrency(attrs.base_price_per_sqm) : null}
        />
        <AttributeRow
          label="Floor Premium"
          value={attrs.floor_premium != null ? formatCurrency(attrs.floor_premium) : null}
        />
        <AttributeRow
          label="View Premium"
          value={attrs.view_premium != null ? formatCurrency(attrs.view_premium) : null}
        />
        <AttributeRow
          label="Corner Premium"
          value={attrs.corner_premium != null ? formatCurrency(attrs.corner_premium) : null}
        />
        <AttributeRow
          label="Size Adjustment"
          value={attrs.size_adjustment != null ? formatCurrency(attrs.size_adjustment) : null}
        />
        <AttributeRow
          label="Custom Adjustment"
          value={attrs.custom_adjustment != null ? formatCurrency(attrs.custom_adjustment) : null}
        />
      </dl>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Layer 3 — Commercial Pricing Record section
// ---------------------------------------------------------------------------

function PricingRecordSection({
  record,
  unitId,
}: {
  record: UnitPricingRecord;
  unitId: string;
}) {
  return (
    <div className={styles.pricingSection}>
      <div className={styles.pricingSectionHeader}>
        <h3 className={styles.pricingSectionTitle}>
          Pricing Record
          <span className={styles.pricingSectionBadge}>Layer 3</span>
        </h3>
        <Link
          href={`/units-pricing?action=editPricing&target=${unitId}`}
          className={styles.sectionEditLink}
        >
          Edit Pricing Record
        </Link>
      </div>
      <p className={styles.pricingSectionSubtitle}>
        Stored commercial pricing decision: approved price, workflow status, and analyst notes.
      </p>
      <dl className={styles.pricingSectionGrid}>
        <AttributeRow
          label="Approved Base Price"
          value={formatCurrency(record.base_price)}
        />
        <AttributeRow
          label="Commercial Adjustment"
          value={formatCurrency(record.manual_adjustment)}
        />
        <AttributeRow
          label="Final Approved Price"
          value={formatCurrency(record.final_price)}
        />
        <AttributeRow label="Currency" value={record.currency} />
        <AttributeRow label="Pricing Status" value={record.pricing_status} />
        {record.notes && <AttributeRow label="Notes" value={record.notes} />}
      </dl>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Shared helper
// ---------------------------------------------------------------------------

function AttributeRow({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <>
      <dt className={styles.pricingSectionLabel}>{label}</dt>
      <dd className={styles.pricingSectionValue} style={{ textTransform: "capitalize" }}>
        {value ?? <span className={styles.notSet}>—</span>}
      </dd>
    </>
  );
}
