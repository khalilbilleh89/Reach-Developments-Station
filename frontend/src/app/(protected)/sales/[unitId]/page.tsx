"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { PageContainer } from "@/components/shell/PageContainer";
import { SalesUnitSummary } from "@/components/sales/SalesUnitSummary";
import { SalesReadinessCard } from "@/components/sales/SalesReadinessCard";
import { ApprovedExceptionPanel } from "@/components/sales/ApprovedExceptionPanel";
import { ContractActionPanel } from "@/components/sales/ContractActionPanel";
import { PaymentPlanPreview } from "@/components/sales/PaymentPlanPreview";
import { getUnitSaleWorkflow } from "@/lib/sales-api";
import type { SalesWorkflowDetail } from "@/lib/sales-types";
import styles from "@/styles/sales-workflow.module.css";

interface SalesWorkflowDetailPageProps {
  params: { unitId: string };
}

/**
 * SalesWorkflowDetailPage — guided sale workflow page for a specific unit.
 *
 * Displays the full commercial picture for a single unit:
 *   - Unit summary (number, type, status, area, pricing)
 *   - Commercial readiness status
 *   - Approved exceptions panel
 *   - Contract action panel
 *   - Payment plan preview (read-only)
 *
 * All data is sourced from the backend via getUnitSaleWorkflow().
 * No business logic or calculations are performed on the frontend.
 *
 * Note: The projectId is extracted from the referrer/session context.
 * For now we pass an empty string and let the API wrapper handle graceful
 * fallbacks when project context is unavailable at the URL level.
 */
export default function SalesWorkflowDetailPage({
  params,
}: SalesWorkflowDetailPageProps) {
  const { unitId } = params;
  const [detail, setDetail] = useState<SalesWorkflowDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    // Project context: pass an empty string; the API layer fetches exceptions
    // using the unit's project_id which is embedded in the exception records.
    // When no project_id is known at this route level, exceptions fall back
    // to an empty list gracefully.
    getUnitSaleWorkflow("", unitId)
      .then(setDetail)
      .catch((err: unknown) => {
        setError(
          err instanceof Error ? err.message : "Failed to load sales workflow.",
        );
      })
      .finally(() => setLoading(false));
  }, [unitId]);

  const title = detail
    ? `Unit ${detail.unit.unit_number} — Sales Workflow`
    : "Sales Workflow";

  const hasApprovedException = detail
    ? detail.approvedExceptions.length > 0
    : false;

  return (
    <PageContainer title={title} subtitle="Guided commercial sale workflow.">
      <Link
        href="/sales"
        className={styles.backLink}
        aria-label="Back to sales queue"
      >
        ← Back to Sales
      </Link>

      {loading && (
        <div className={styles.loadingState}>Loading sales workflow…</div>
      )}

      {error && <div className={styles.errorState}>{error}</div>}

      {detail && (
        <div className={styles.detailLayout}>
          {/* Unit summary — full width */}
          <div className={styles.detailFullWidth}>
            <SalesUnitSummary unit={detail.unit} pricing={detail.pricing} />
          </div>

          {/* Readiness card */}
          <SalesReadinessCard
            unit={detail.unit}
            pricing={detail.pricing}
            hasApprovedException={hasApprovedException}
            contractStatus={detail.contractAction.contractStatus}
            readiness={
              hasApprovedException && detail.contractAction.contractStatus !== "active"
                ? "ready"
                : detail.contractAction.contractStatus === "active"
                  ? "under_contract"
                  : detail.pricing === null
                    ? "missing_pricing"
                    : "ready"
            }
          />

          {/* Contract action panel */}
          <ContractActionPanel contractAction={detail.contractAction} />

          {/* Approved exception panel — full width */}
          <div className={styles.detailFullWidth}>
            <ApprovedExceptionPanel exceptions={detail.approvedExceptions} />
          </div>

          {/* Payment plan preview — full width */}
          <div className={styles.detailFullWidth}>
            <PaymentPlanPreview preview={detail.paymentPlanPreview} />
          </div>
        </div>
      )}
    </PageContainer>
  );
}
