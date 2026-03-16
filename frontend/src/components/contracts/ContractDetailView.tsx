"use client";

import React, { useEffect, useState, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import { PageContainer } from "@/components/shell/PageContainer";
import { CreatePaymentPlanModal } from "@/components/contracts/CreatePaymentPlanModal";
import { InstallmentsTable } from "@/components/contracts/InstallmentsTable";
import { ReceivablesTable } from "@/components/contracts/ReceivablesTable";
import {
  createPaymentPlan,
  listInstallments,
  type PaymentPlanCreatePayload,
} from "@/lib/payment-plans-api";
import {
  generateReceivables,
  listContractReceivables,
} from "@/lib/receivables-api";
import { ApiError } from "@/lib/api-client";
import type { PaymentPlan, Installment } from "@/lib/payment-plans-types";
import type { Receivable } from "@/lib/receivables-types";
import { formatCurrency } from "@/lib/format-utils";
import styles from "@/styles/payment-plans.module.css";

/**
 * ContractDetailView — contract-level view showing payment plan section.
 *
 * Reads ?contractId= from the URL query string so the view is compatible with
 * Next.js static export (output: "export").
 *
 * Shows:
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

  // Receivables state
  const [receivables, setReceivables] = useState<Receivable[]>([]);
  const [receivablesLoading, setReceivablesLoading] = useState(false);
  const [receivablesError, setReceivablesError] = useState<string | null>(null);
  const [generatingReceivables, setGeneratingReceivables] = useState(false);

  const loadPlan = useCallback(async () => {
    if (!contractId) {
      setLoading(false);
      setError("No contract ID provided.");
      return;
    }
    // Reset stale state from a previous contract before fetching.
    setPlan(null);
    setInstallments([]);
    setReceivables([]);
    setLoading(true);
    setError(null);
    setReceivablesError(null);
    try {
      // Try to load the installment schedule for this contract.
      const schedule = await listInstallments(contractId);
      if (schedule.total > 0) {
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
      } else {
        setInstallments([]);
      }
    } catch (err: unknown) {
      // 404 means no plan exists yet — that is expected; show the CTA.
      if (err instanceof ApiError && err.status === 404) {
        setInstallments([]);
      } else {
        setError("Failed to load payment plan.");
      }
    } finally {
      setLoading(false);
    }
  }, [contractId]);

  const loadReceivables = useCallback(async () => {
    if (!contractId) return;
    setReceivablesLoading(true);
    setReceivablesError(null);
    try {
      const data = await listContractReceivables(contractId);
      setReceivables(data.items);
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 404) {
        setReceivables([]);
      } else {
        setReceivablesError("Failed to load receivables.");
      }
    } finally {
      setReceivablesLoading(false);
    }
  }, [contractId]);

  useEffect(() => {
    loadPlan();
  }, [loadPlan]);

  useEffect(() => {
    loadReceivables();
  }, [loadReceivables]);

  async function handleCreatePlan(payload: PaymentPlanCreatePayload): Promise<PaymentPlan> {
    const created = await createPaymentPlan(payload);
    setPlan(created);
    setInstallments(created.installments);
    return created;
  }

  async function handleGenerateReceivables(): Promise<void> {
    if (!contractId) return;
    setGeneratingReceivables(true);
    setReceivablesError(null);
    try {
      const result = await generateReceivables(contractId);
      setReceivables(result.items);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setReceivablesError(err.message || "Failed to generate receivables.");
      } else {
        setReceivablesError("Failed to generate receivables.");
      }
    } finally {
      setGeneratingReceivables(false);
    }
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

          {/* Receivables section */}
          <section className={styles.section} aria-label="Receivables">
            <div className={styles.sectionHeader}>
              <h2 className={styles.sectionTitle}>Receivables</h2>
            </div>

            {!hasPlan && (
              <div className={styles.emptyState}>
                <p className={styles.emptyStateBody}>
                  A payment plan is required before generating receivables.
                </p>
              </div>
            )}

            {hasPlan && receivablesLoading && (
              <div className={styles.loadingState}>Loading receivables…</div>
            )}

            {hasPlan && !receivablesLoading && receivablesError && (
              <div className={styles.errorState}>{receivablesError}</div>
            )}

            {hasPlan && !receivablesLoading && !receivablesError && receivables.length === 0 && (
              <div className={styles.emptyState}>
                <p className={styles.emptyStateTitle}>No receivables</p>
                <p className={styles.emptyStateBody}>
                  Receivables track each installment as a collectible financial obligation.
                </p>
                <button
                  type="button"
                  className={styles.createButton}
                  onClick={handleGenerateReceivables}
                  disabled={generatingReceivables}
                >
                  {generatingReceivables ? "Generating…" : "Generate Receivables"}
                </button>
              </div>
            )}

            {hasPlan && !receivablesLoading && receivables.length > 0 && (
              <ReceivablesTable receivables={receivables} />
            )}
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
