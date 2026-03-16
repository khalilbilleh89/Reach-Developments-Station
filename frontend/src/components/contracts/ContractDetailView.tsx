"use client";

import React, { useEffect, useState, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import { PageContainer } from "@/components/shell/PageContainer";
import { CreatePaymentPlanModal } from "@/components/contracts/CreatePaymentPlanModal";
import { InstallmentsTable } from "@/components/contracts/InstallmentsTable";
import {
  createPaymentPlan,
  listInstallments,
  type PaymentPlanCreatePayload,
} from "@/lib/payment-plans-api";
import type { PaymentPlan, Installment } from "@/lib/payment-plans-types";
import { formatCurrency } from "@/lib/format-utils";
import styles from "@/styles/payment-plans.module.css";

interface ContractSummary {
  id: string;
  contractNumber: string;
  contractPrice: number;
  status: string;
}

/**
 * ContractDetailView — contract-level view showing payment plan section.
 *
 * Reads ?contractId= from the URL query string so the view is compatible with
 * Next.js static export (output: "export").
 *
 * Shows:
 *   - Contract summary (number, price, status)
 *   - Payment Plan section
 *       • If no plan exists: "Create Payment Plan" button
 *       • If plan exists: plan summary + InstallmentsTable
 *
 * All data is sourced from the backend API. No financial calculations are
 * performed on the frontend.
 */
export default function ContractDetailView() {
  const searchParams = useSearchParams();
  const contractId = searchParams.get("contractId") ?? "";

  const [plan, setPlan] = useState<PaymentPlan | null>(null);
  const [installments, setInstallments] = useState<Installment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);

  const loadPlan = useCallback(async () => {
    if (!contractId) {
      setLoading(false);
      setError("No contract ID provided.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      // Try to load the installment schedule for this contract.
      const schedule = await listInstallments(contractId);
      if (schedule.total > 0) {
        // Map schedule items to Installment shape for the table.
        setInstallments(
          schedule.items.map((item) => ({
            id: item.id,
            installment_number: item.installment_number,
            due_date: String(item.due_date),
            due_amount: item.due_amount,
            status: item.status as Installment["status"],
            notes: item.notes,
          })),
        );
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      // 404 means no plan exists yet — that is expected.
      if (!msg.includes("404")) {
        setError("Failed to load payment plan.");
      }
    } finally {
      setLoading(false);
    }
  }, [contractId]);

  useEffect(() => {
    loadPlan();
  }, [loadPlan]);

  async function handleCreatePlan(payload: PaymentPlanCreatePayload): Promise<PaymentPlan> {
    const created = await createPaymentPlan(payload);
    setPlan(created);
    setInstallments(created.installments);
    return created;
  }

  const hasPlan = plan !== null || installments.length > 0;

  return (
    <PageContainer
      title={contractId ? `Contract — Payment Plan` : "Contract Detail"}
      subtitle="Payment plan and installment schedule for this contract."
    >
      {loading && (
        <div className={styles.loadingState}>Loading contract…</div>
      )}

      {!loading && error && (
        <div className={styles.errorState}>{error}</div>
      )}

      {!loading && !error && (
        <>
          {/* Payment Plan section */}
          <section className={styles.section} aria-label="Payment Plan">
            <div className={styles.sectionHeader}>
              <h2 className={styles.sectionTitle}>Payment Plan</h2>
              {hasPlan && plan && (
                <span className={styles.sectionMeta}>
                  {plan.plan_name} &mdash; {plan.total_installments} installments &mdash;{" "}
                  {formatCurrency(plan.total_due)} total
                </span>
              )}
            </div>

            {!hasPlan && (
              <div className={styles.emptyState}>
                <p className={styles.emptyStateTitle}>No payment plan</p>
                <p className={styles.emptyStateBody}>
                  No payment schedule has been created for this contract.
                </p>
                <button
                  type="button"
                  className={styles.createButton}
                  onClick={() => setShowModal(true)}
                >
                  Create Payment Plan
                </button>
              </div>
            )}

            {hasPlan && <InstallmentsTable installments={installments} />}
          </section>
        </>
      )}

      {showModal && contractId && (
        <CreatePaymentPlanModal
          contractId={contractId}
          onSubmit={handleCreatePlan}
          onClose={() => setShowModal(false)}
        />
      )}
    </PageContainer>
  );
}
