"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { PageContainer } from "@/components/shell/PageContainer";
import { SalesUnitSummary } from "@/components/sales/SalesUnitSummary";
import { SalesReadinessCard } from "@/components/sales/SalesReadinessCard";
import { ApprovedExceptionPanel } from "@/components/sales/ApprovedExceptionPanel";
import { ContractActionPanel } from "@/components/sales/ContractActionPanel";
import { PaymentPlanPreview } from "@/components/sales/PaymentPlanPreview";
import { getUnitSaleWorkflow } from "@/lib/sales-api";
import type { SalesWorkflowDetail } from "@/lib/sales-types";
import styles from "@/styles/sales-workflow.module.css";

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
 * Project context is received via the `?projectId=` query parameter, which
 * the sales queue page injects when navigating here. Without a valid
 * projectId, approved exceptions will not load (the API layer returns [] and
 * shows an informational warning instead of issuing a malformed request).
 *
 * All data is sourced from the backend via getUnitSaleWorkflow().
 * No business logic or calculations are performed on the frontend.
 */
export default function SalesWorkflowDetailPage() {
  const { unitId } = useParams<{ unitId: string }>();
  const searchParams = useSearchParams();
  const projectId = searchParams.get("projectId") ?? "";

  const [detail, setDetail] = useState<SalesWorkflowDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getUnitSaleWorkflow(projectId, unitId)
      .then(setDetail)
      .catch((err: unknown) => {
        setError(
          err instanceof Error ? err.message : "Failed to load sales workflow.",
        );
      })
      .finally(() => setLoading(false));
  }, [projectId, unitId]);

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

      {!projectId && (
        <div className={styles.errorState}>
          No project context available. Navigate here from the sales queue to
          load approved exceptions and full readiness data.
        </div>
      )}

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
            hasPendingException={detail.hasPendingException}
            contractStatus={detail.contractAction.contractStatus}
            readiness={detail.readiness}
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
