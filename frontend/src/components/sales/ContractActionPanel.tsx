"use client";

import React from "react";
import type { ContractActionState } from "@/lib/sales-types";
import { contractStatusLabel } from "@/lib/sales-types";
import styles from "@/styles/sales-workflow.module.css";

interface ContractActionPanelProps {
  contractAction: ContractActionState;
}

/**
 * ContractActionPanel — shows contract-related action entry point.
 *
 * Displays the current contract state and whether contract creation is
 * available for the unit. This panel is informational only — it does not
 * trigger contract creation directly (backend mutation is out of scope for
 * this PR). When a contract already exists, its details are displayed.
 *
 * No business logic is applied here — the `contractAction` prop is derived
 * from backend data in sales-api.ts.
 */
export function ContractActionPanel({ contractAction }: ContractActionPanelProps) {
  const { kind, contractId, contractNumber, contractStatus } = contractAction;

  return (
    <div className={styles.contractPanel}>
      <p className={styles.contractPanelTitle}>Contract Action</p>

      <div className={styles.contractStatus}>
        {kind === "available" && (
          <>
            <p className={styles.contractStatusLabel}>
              Contract creation available
            </p>
            <div className={styles.contractAvailableNote}>
              This unit is available for contract initiation. Use the contract
              creation workflow to proceed.
            </div>
          </>
        )}

        {kind === "already_active" && (
          <>
            <p className={styles.contractStatusLabel}>
              Active contract exists
            </p>
            <div className={styles.contractMeta}>
              {contractNumber && (
                <div className={styles.contractMetaRow}>
                  <span className={styles.contractMetaKey}>Contract #</span>
                  <span className={styles.contractMetaValue}>
                    {contractNumber}
                  </span>
                </div>
              )}
              {contractId && (
                <div className={styles.contractMetaRow}>
                  <span className={styles.contractMetaKey}>Contract ID</span>
                  <span className={styles.contractMetaValue}>{contractId}</span>
                </div>
              )}
              {contractStatus && (
                <div className={styles.contractMetaRow}>
                  <span className={styles.contractMetaKey}>Status</span>
                  <span className={styles.contractMetaValue}>
                    {contractStatusLabel(contractStatus)}
                  </span>
                </div>
              )}
            </div>
          </>
        )}

        {kind === "already_draft" && (
          <>
            <p className={styles.contractStatusLabel}>
              Draft contract on file
            </p>
            <div className={styles.contractMeta}>
              {contractNumber && (
                <div className={styles.contractMetaRow}>
                  <span className={styles.contractMetaKey}>Contract #</span>
                  <span className={styles.contractMetaValue}>
                    {contractNumber}
                  </span>
                </div>
              )}
              {contractId && (
                <div className={styles.contractMetaRow}>
                  <span className={styles.contractMetaKey}>Contract ID</span>
                  <span className={styles.contractMetaValue}>{contractId}</span>
                </div>
              )}
              <div className={styles.contractAvailableNote}>
                A draft contract exists. Activate it to proceed with the sale.
              </div>
            </div>
          </>
        )}

        {kind === "unavailable" && (
          <>
            <p className={styles.contractStatusLabel}>
              Contract creation unavailable
            </p>
            <div className={styles.contractUnavailableNote}>
              {contractStatus
                ? `This unit has a ${contractStatusLabel(contractStatus).toLowerCase()} contract.`
                : "This unit is not in a state that permits contract creation."}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
