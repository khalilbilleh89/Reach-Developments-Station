"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { PageContainer } from "@/components/shell/PageContainer";
import { ContractPaymentHeader } from "@/components/payment-plans/ContractPaymentHeader";
import { InstallmentScheduleTable } from "@/components/payment-plans/InstallmentScheduleTable";
import { CollectionsProgressCard } from "@/components/payment-plans/CollectionsProgressCard";
import { OverdueInstallmentsPanel } from "@/components/payment-plans/OverdueInstallmentsPanel";
import { getContractPaymentPlan } from "@/lib/payment-plans-api";
import type { PaymentPlanDetail } from "@/lib/payment-plans-types";
import { formatCurrency } from "@/lib/format-utils";
import styles from "@/styles/payment-plans.module.css";

interface PaymentPlanDetailPageProps {
  params: { contractId: string };
}

/**
 * PaymentPlanDetailPage — contract-level payment plan detail page.
 *
 * Displays:
 *   - Contract summary (ContractPaymentHeader)
 *   - Collections progress card
 *   - Overdue installments panel (hidden when no overdue items)
 *   - Outstanding balance card
 *   - Full installment schedule table
 *
 * All data is sourced from the backend via getContractPaymentPlan().
 * No business logic or calculations are performed on the frontend.
 */
export default function PaymentPlanDetailPage({
  params,
}: PaymentPlanDetailPageProps) {
  const { contractId } = params;

  const [detail, setDetail] = useState<PaymentPlanDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getContractPaymentPlan(contractId)
      .then(setDetail)
      .catch((err: unknown) => {
        setError(
          err instanceof Error
            ? err.message
            : "Failed to load payment plan.",
        );
      })
      .finally(() => setLoading(false));
  }, [contractId]);

  const title = detail
    ? `Contract ${detail.contractNumber} — Payment Plan`
    : "Payment Plan Detail";

  return (
    <PageContainer
      title={title}
      subtitle="Installment schedule, collection progress, and outstanding balance."
    >
      <Link
        href="/payment-plans"
        className={styles.backLink}
        aria-label="Back to payment plans"
      >
        ← Back to Payment Plans
      </Link>

      {loading && (
        <div className={styles.loadingState}>Loading payment plan…</div>
      )}

      {error && <div className={styles.errorState}>{error}</div>}

      {detail && (
        <div className={styles.detailLayout}>
          {/* Contract header — full width */}
          <div className={styles.detailFullWidth}>
            <ContractPaymentHeader detail={detail} />
          </div>

          {/* Collections progress */}
          <CollectionsProgressCard summary={detail.collectionSummary} />

          {/* Outstanding balance card */}
          <div className={styles.summaryCard}>
            <p className={styles.summaryCardTitle}>Outstanding Balance</p>
            <div className={styles.summaryGrid}>
              <div className={styles.summaryItem}>
                <span className={styles.summaryItemLabel}>Total Due</span>
                <span className={styles.summaryItemValueLarge}>
                  {formatCurrency(detail.collectionSummary.totalDue)}
                </span>
              </div>
              <div className={styles.summaryItem}>
                <span className={styles.summaryItemLabel}>Total Collected</span>
                <span className={styles.summaryItemValueLarge}>
                  {formatCurrency(detail.collectionSummary.totalReceived)}
                </span>
              </div>
              <div className={styles.summaryItem}>
                <span className={styles.summaryItemLabel}>Outstanding</span>
                <span className={styles.summaryItemValueLarge}>
                  {formatCurrency(detail.collectionSummary.totalOutstanding)}
                </span>
              </div>
            </div>
          </div>

          {/* Overdue installments panel — full width (hidden when none) */}
          {detail.overdueInstallments.length > 0 && (
            <div className={styles.detailFullWidth}>
              <OverdueInstallmentsPanel
                overdueInstallments={detail.overdueInstallments}
              />
            </div>
          )}

          {/* Installment schedule table — full width */}
          <div className={styles.detailFullWidth}>
            <div className={styles.summaryCard}>
              <p className={styles.summaryCardTitle}>Installment Schedule</p>
              <InstallmentScheduleTable rows={detail.schedule} />
            </div>
          </div>
        </div>
      )}
    </PageContainer>
  );
}
