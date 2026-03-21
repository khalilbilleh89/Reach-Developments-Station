"use client";

import React, { useCallback, useEffect, useState } from "react";
import { PageContainer } from "@/components/shell/PageContainer";
import {
  generateCollectionsAlerts,
  getCollectionsAlerts,
  matchPaymentReceipt,
  resolveCollectionsAlert,
} from "@/lib/finance-api";
import type {
  AlertSeverity,
  CollectionsAlert,
  ReceiptMatchResult,
} from "@/lib/finance-types";
import { formatCurrency } from "@/lib/format-utils";
import styles from "@/styles/finance-dashboard.module.css";

/**
 * Finance — Collections Alerts Dashboard.
 *
 * Sections:
 *   1. Overdue Alerts Table — lists active alerts with severity, days overdue,
 *      outstanding balance, and a resolve action.
 *   2. Manual Receipt Matching — enter a contract ID and payment amount to
 *      see how the payment would be allocated across installments.
 *
 * Data sources:
 *   GET  /finance/collections/alerts             — active alert list
 *   POST /finance/collections/alerts/generate    — scan and generate alerts
 *   POST /finance/collections/alerts/{id}/resolve — resolve an alert
 *   POST /finance/payments/match-receipt          — match a payment
 */

const SEVERITY_LABELS: Record<AlertSeverity, string> = {
  warning: "Warning",
  critical: "Critical",
  high_risk: "High Risk",
};

const SEVERITY_ORDER: AlertSeverity[] = ["warning", "critical", "high_risk"];

function severityLabel(severity: AlertSeverity): string {
  return SEVERITY_LABELS[severity] ?? severity;
}

// ---------------------------------------------------------------------------
// Collections Alerts Section
// ---------------------------------------------------------------------------

interface AlertsTableProps {
  alerts: CollectionsAlert[];
  onResolve: (alertId: string) => void;
  resolvingId: string | null;
}

function AlertsTable({ alerts, onResolve, resolvingId }: AlertsTableProps) {
  if (alerts.length === 0) {
    return <p>No active alerts.</p>;
  }
  return (
    <table className={styles.dataTable ?? undefined}>
      <thead>
        <tr>
          <th>Contract</th>
          <th>Installment</th>
          <th>Severity</th>
          <th>Days Overdue</th>
          <th>Outstanding</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody>
        {alerts.map((a) => (
          <tr key={a.alertId}>
            <td title={a.contractId}>{a.contractId.slice(0, 8)}…</td>
            <td title={a.installmentId}>{a.installmentId.slice(0, 8)}…</td>
            <td>{severityLabel(a.severity)}</td>
            <td>{a.daysOverdue}</td>
            <td>{formatCurrency(a.outstandingBalance)}</td>
            <td>
              <button
                disabled={resolvingId === a.alertId}
                onClick={() => onResolve(a.alertId)}
              >
                {resolvingId === a.alertId ? "Resolving…" : "Resolve"}
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// ---------------------------------------------------------------------------
// Receipt Matching Section
// ---------------------------------------------------------------------------

interface MatchResult {
  result: ReceiptMatchResult | null;
  error: string | null;
}

function ReceiptMatchingPanel() {
  const [contractId, setContractId] = useState("");
  const [paymentAmount, setPaymentAmount] = useState("");
  const [loading, setLoading] = useState(false);
  const [match, setMatch] = useState<MatchResult>({ result: null, error: null });

  const handleMatch = async () => {
    const amount = parseFloat(paymentAmount);
    if (!contractId.trim() || isNaN(amount) || amount <= 0) {
      setMatch({ result: null, error: "Enter a valid contract ID and amount > 0." });
      return;
    }
    setLoading(true);
    setMatch({ result: null, error: null });
    try {
      const result = await matchPaymentReceipt(contractId.trim(), amount);
      setMatch({ result, error: null });
    } catch (err: unknown) {
      setMatch({
        result: null,
        error: err instanceof Error ? err.message : "Match failed.",
      });
    } finally {
      setLoading(false);
    }
  };

  const strategyLabel: Record<string, string> = {
    exact: "Exact Match",
    partial: "Partial Payment",
    multi_installment: "Multi-Installment",
    unmatched: "Unmatched",
  };

  return (
    <section>
      <h3>Manual Receipt Matching</h3>
      <p>Enter a contract reference and payment amount to preview installment allocation.</p>
      <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginBottom: "1rem" }}>
        <input
          type="text"
          placeholder="Contract ID"
          value={contractId}
          onChange={(e) => setContractId(e.target.value)}
          aria-label="Contract ID"
          style={{ minWidth: "240px" }}
        />
        <input
          type="number"
          placeholder="Payment Amount"
          value={paymentAmount}
          onChange={(e) => setPaymentAmount(e.target.value)}
          aria-label="Payment Amount"
          min={0.01}
          step={0.01}
          style={{ minWidth: "160px" }}
        />
        <button onClick={handleMatch} disabled={loading}>
          {loading ? "Matching…" : "Match Receipt"}
        </button>
      </div>

      {match.error && <p className={styles.errorText}>{match.error}</p>}

      {match.result && (
        <div>
          <p>
            <strong>Strategy:</strong>{" "}
            {strategyLabel[match.result.strategy] ?? match.result.strategy}
          </p>
          <p>
            <strong>Payment Amount:</strong>{" "}
            {formatCurrency(match.result.paymentAmount)}
          </p>
          <p>
            <strong>Unallocated:</strong>{" "}
            {formatCurrency(match.result.unallocatedAmount)}
          </p>
          {match.result.allocations.length > 0 && (
            <>
              <h4>Allocation Breakdown</h4>
              <table className={styles.dataTable ?? undefined}>
                <thead>
                  <tr>
                    <th>Installment</th>
                    <th>Allocated Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {match.result.allocations.map((alloc) => (
                    <tr key={alloc.installmentId}>
                      <td title={alloc.installmentId}>
                        {alloc.installmentId.slice(0, 8)}…
                      </td>
                      <td>{formatCurrency(alloc.allocatedAmount)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </div>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------

export default function CollectionsAlertsPage() {
  const [alerts, setAlerts] = useState<CollectionsAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [severityFilter, setSeverityFilter] = useState<AlertSeverity | "">("");
  const [resolvingId, setResolvingId] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);

  const loadAlerts = useCallback(async (severity?: AlertSeverity) => {
    setLoading(true);
    setError(null);
    try {
      const data = await getCollectionsAlerts(severity || undefined);
      setAlerts(data.items);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load alerts.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAlerts(severityFilter || undefined);
  }, [severityFilter, loadAlerts]);

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const data = await generateCollectionsAlerts();
      setAlerts(data.items);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to generate alerts.");
    } finally {
      setGenerating(false);
    }
  };

  const handleResolve = async (alertId: string) => {
    setResolvingId(alertId);
    try {
      await resolveCollectionsAlert(alertId);
      // Refresh list after resolution.
      await loadAlerts(severityFilter || undefined);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to resolve alert.");
    } finally {
      setResolvingId(null);
    }
  };

  const filteredAlerts =
    severityFilter
      ? alerts.filter((a) => a.severity === severityFilter)
      : alerts;

  return (
    <PageContainer
      title="Collections — Alerts"
      subtitle="Monitor overdue installment alerts and manage payment reconciliation."
    >
      {/* KPI summary */}
      <div className={styles.kpiGrid}>
        <div className={styles.kpiCard}>
          <div className={styles.kpiLabel}>Active Alerts</div>
          <div className={styles.kpiValue}>{alerts.length}</div>
        </div>
        {SEVERITY_ORDER.map((sev) => {
          const count = alerts.filter((a) => a.severity === sev).length;
          return (
            <div key={sev} className={styles.kpiCard}>
              <div className={styles.kpiLabel}>{severityLabel(sev)}</div>
              <div className={styles.kpiValue}>{count}</div>
            </div>
          );
        })}
      </div>

      {/* Toolbar */}
      <div
        style={{
          display: "flex",
          gap: "0.75rem",
          flexWrap: "wrap",
          alignItems: "center",
          margin: "1rem 0",
        }}
      >
        <label htmlFor="severity-filter">Filter by severity:</label>
        <select
          id="severity-filter"
          value={severityFilter}
          onChange={(e) => setSeverityFilter(e.target.value as AlertSeverity | "")}
          aria-label="Severity filter"
        >
          <option value="">All</option>
          {SEVERITY_ORDER.map((s) => (
            <option key={s} value={s}>
              {severityLabel(s)}
            </option>
          ))}
        </select>

        <button onClick={handleGenerate} disabled={generating}>
          {generating ? "Generating…" : "Generate Alerts"}
        </button>
      </div>

      {error && <p className={styles.errorText}>{error}</p>}

      {/* Alerts table */}
      {loading ? (
        <p>Loading alerts…</p>
      ) : (
        <AlertsTable
          alerts={filteredAlerts}
          onResolve={handleResolve}
          resolvingId={resolvingId}
        />
      )}

      {/* Receipt matching */}
      <ReceiptMatchingPanel />
    </PageContainer>
  );
}
