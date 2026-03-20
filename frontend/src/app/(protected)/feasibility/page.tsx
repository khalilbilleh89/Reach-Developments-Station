"use client";

import React, { useCallback, useEffect, useState } from "react";
import { PageContainer } from "@/components/shell/PageContainer";
import { MetricCard } from "@/components/dashboard/MetricCard";
import {
  listFeasibilityRuns,
  createFeasibilityRun,
  updateFeasibilityRun,
} from "@/lib/feasibility-api";
import type {
  FeasibilityRun,
  FeasibilityRunCreate,
  FeasibilityScenarioType,
} from "@/lib/feasibility-types";
import styles from "@/styles/demo-shell.module.css";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatScenarioType(type: FeasibilityScenarioType): string {
  switch (type) {
    case "base":
      return "Base";
    case "upside":
      return "Upside";
    case "downside":
      return "Downside";
    case "investor":
      return "Investor";
    default:
      return type;
  }
}

function scenarioBadgeClass(type: FeasibilityScenarioType): string {
  switch (type) {
    case "base":
      return styles.badgeBlue;
    case "upside":
      return styles.badgeGreen;
    case "downside":
      return styles.badgeRed;
    case "investor":
      return styles.badgePurple;
    default:
      return styles.badgeGray;
  }
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

// ---------------------------------------------------------------------------
// Create run modal
// ---------------------------------------------------------------------------

interface CreateRunModalProps {
  onClose: () => void;
  onCreated: () => void;
}

function CreateRunModal({ onClose, onCreated }: CreateRunModalProps) {
  const [scenarioName, setScenarioName] = useState("");
  const [scenarioType, setScenarioType] =
    useState<FeasibilityScenarioType>("base");
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!scenarioName.trim()) {
        setError("Scenario name is required.");
        return;
      }
      setSubmitting(true);
      setError(null);
      const data: FeasibilityRunCreate = {
        scenario_name: scenarioName.trim(),
        scenario_type: scenarioType,
        notes: notes.trim() || null,
      };
      try {
        await createFeasibilityRun(data);
        onCreated();
      } catch (err: unknown) {
        setError(
          err instanceof Error
            ? err.message
            : "Failed to create feasibility run.",
        );
      } finally {
        setSubmitting(false);
      }
    },
    [scenarioName, scenarioType, notes, onCreated],
  );

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="create-run-dialog-title"
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.4)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1000,
      }}
    >
      <div
        style={{
          background: "var(--color-surface)",
          borderRadius: 12,
          padding: 32,
          width: 480,
          maxWidth: "90vw",
          boxShadow: "0 20px 40px rgba(0,0,0,0.15)",
        }}
      >
        <h2
          id="create-run-dialog-title"
          style={{ margin: "0 0 24px", fontSize: "1.125rem", fontWeight: 600 }}
        >
          New Feasibility Run
        </h2>
        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: 16 }}>
            <label
              htmlFor="create-run-scenario-name"
              style={{
                display: "block",
                marginBottom: 6,
                fontSize: "0.875rem",
                fontWeight: 500,
              }}
            >
              Scenario Name *
            </label>
            <input
              id="create-run-scenario-name"
              type="text"
              value={scenarioName}
              onChange={(e) => setScenarioName(e.target.value)}
              placeholder="e.g. Base Case Q1 2025"
              style={{
                width: "100%",
                padding: "8px 12px",
                border: "1px solid var(--color-border)",
                borderRadius: 6,
                fontSize: "0.875rem",
                boxSizing: "border-box",
              }}
              required
            />
          </div>
          <div style={{ marginBottom: 16 }}>
            <label
              htmlFor="create-run-scenario-type"
              style={{
                display: "block",
                marginBottom: 6,
                fontSize: "0.875rem",
                fontWeight: 500,
              }}
            >
              Scenario Type
            </label>
            <select
              id="create-run-scenario-type"
              value={scenarioType}
              onChange={(e) =>
                setScenarioType(e.target.value as FeasibilityScenarioType)
              }
              style={{
                width: "100%",
                padding: "8px 12px",
                border: "1px solid var(--color-border)",
                borderRadius: 6,
                fontSize: "0.875rem",
                background: "var(--color-surface)",
                boxSizing: "border-box",
              }}
            >
              <option value="base">Base</option>
              <option value="upside">Upside</option>
              <option value="downside">Downside</option>
              <option value="investor">Investor</option>
            </select>
          </div>
          <div style={{ marginBottom: 24 }}>
            <label
              htmlFor="create-run-notes"
              style={{
                display: "block",
                marginBottom: 6,
                fontSize: "0.875rem",
                fontWeight: 500,
              }}
            >
              Notes
            </label>
            <textarea
              id="create-run-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Optional notes about this scenario…"
              rows={3}
              style={{
                width: "100%",
                padding: "8px 12px",
                border: "1px solid var(--color-border)",
                borderRadius: 6,
                fontSize: "0.875rem",
                boxSizing: "border-box",
                resize: "vertical",
              }}
            />
          </div>
          {error && (
            <p
              role="alert"
              style={{
                color: "#b91c1c",
                fontSize: "0.875rem",
                marginBottom: 16,
              }}
            >
              {error}
            </p>
          )}
          <div style={{ display: "flex", gap: 12, justifyContent: "flex-end" }}>
            <button
              type="button"
              onClick={onClose}
              style={{
                padding: "8px 20px",
                border: "1px solid var(--color-border)",
                borderRadius: 6,
                background: "transparent",
                cursor: "pointer",
                fontSize: "0.875rem",
              }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              style={{
                padding: "8px 20px",
                border: "none",
                borderRadius: 6,
                background: "var(--color-primary, #2563eb)",
                color: "#fff",
                cursor: submitting ? "not-allowed" : "pointer",
                fontSize: "0.875rem",
                fontWeight: 500,
              }}
            >
              {submitting ? "Creating…" : "Create Run"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------

/**
 * Feasibility page — feasibility run management dashboard.
 *
 * Shows KPI summary and a table of feasibility runs. Supports create
 * and scenario type update operations.
 */
export default function FeasibilityPage() {
  const [runs, setRuns] = useState<FeasibilityRun[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);

  const fetchRuns = useCallback(() => {
    setLoading(true);
    listFeasibilityRuns({ limit: 100 })
      .then((resp) => {
        setRuns(resp.items);
        setTotal(resp.items.length);
        setError(null);
      })
      .catch((err: unknown) => {
        setError(
          err instanceof Error
            ? err.message
            : "Failed to load feasibility runs.",
        );
        setRuns([]);
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    fetchRuns();
  }, [fetchRuns]);

  const handleCreated = useCallback(() => {
    setShowCreateModal(false);
    fetchRuns();
  }, [fetchRuns]);

  const handleScenarioTypeChange = useCallback(
    async (runId: string, newType: FeasibilityScenarioType) => {
      try {
        await updateFeasibilityRun(runId, { scenario_type: newType });
        fetchRuns();
      } catch (err: unknown) {
        setError(
          err instanceof Error
            ? err.message
            : "Failed to update scenario type.",
        );
      }
    },
    [fetchRuns],
  );

  // KPI counts
  const baseCount = runs.filter((r) => r.scenario_type === "base").length;
  const upsideCount = runs.filter((r) => r.scenario_type === "upside").length;
  const downsideCount = runs.filter(
    (r) => r.scenario_type === "downside",
  ).length;
  const investorCount = runs.filter(
    (r) => r.scenario_type === "investor",
  ).length;

  return (
    <PageContainer
      title="Feasibility"
      subtitle="Manage feasibility scenario runs, set assumptions, and review pro forma outputs."
    >
      {/* KPI row */}
      <div className={styles.kpiGrid}>
        <MetricCard title="Total Runs" value={String(total)} />
        <MetricCard title="Base" value={String(baseCount)} />
        <MetricCard title="Upside" value={String(upsideCount)} />
        <MetricCard title="Downside" value={String(downsideCount)} />
      </div>

      {investorCount > 0 && (
        <div
          className={styles.kpiGrid3}
          style={{ marginBottom: "var(--space-6)" }}
        >
          <MetricCard title="Investor" value={String(investorCount)} />
        </div>
      )}

      {/* Toolbar */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "var(--space-4)",
        }}
      >
        <h2 style={{ margin: 0, fontSize: "1rem", fontWeight: 600 }}>
          Feasibility Runs
        </h2>
        <button
          type="button"
          onClick={() => setShowCreateModal(true)}
          style={{
            padding: "8px 20px",
            border: "none",
            borderRadius: 6,
            background: "var(--color-primary, #2563eb)",
            color: "#fff",
            cursor: "pointer",
            fontSize: "0.875rem",
            fontWeight: 500,
          }}
        >
          + New Run
        </button>
      </div>

      {/* Error state */}
      {error && (
        <div
          role="alert"
          style={{
            padding: "12px 16px",
            background: "#fef2f2",
            border: "1px solid #fecaca",
            borderRadius: 8,
            color: "#b91c1c",
            marginBottom: "var(--space-4)",
            fontSize: "0.875rem",
          }}
        >
          {error}
        </div>
      )}

      {/* Loading state */}
      {loading && (
        <div
          style={{
            padding: 40,
            textAlign: "center",
            color: "var(--color-text-muted)",
          }}
        >
          Loading feasibility runs…
        </div>
      )}

      {/* Empty state */}
      {!loading && runs.length === 0 && !error && (
        <div
          style={{
            padding: 60,
            textAlign: "center",
            color: "var(--color-text-muted)",
            background: "var(--color-surface)",
            borderRadius: 8,
            border: "1px solid var(--color-border)",
          }}
        >
          <div style={{ fontSize: "2rem", marginBottom: 12 }}>📐</div>
          <p style={{ margin: 0, fontWeight: 500 }}>No feasibility runs yet</p>
          <p style={{ margin: "8px 0 0", fontSize: "0.875rem" }}>
            Create your first feasibility run to start evaluating development
            scenarios.
          </p>
        </div>
      )}

      {/* Runs table */}
      {!loading && runs.length > 0 && (
        <div className={styles.tableWrapper}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Scenario Name</th>
                <th>Type</th>
                <th>Project</th>
                <th>Notes</th>
                <th>Last Updated</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.id}>
                  <td style={{ fontWeight: 500 }}>{run.scenario_name}</td>
                  <td>
                    <span
                      className={`${styles.badge} ${scenarioBadgeClass(run.scenario_type)}`}
                    >
                      {formatScenarioType(run.scenario_type)}
                    </span>
                  </td>
                  <td
                    style={{
                      fontSize: "0.8rem",
                      color: "var(--color-text-muted)",
                    }}
                  >
                    {run.project_id ? (
                      <span style={{ fontFamily: "monospace" }}>
                        {run.project_id.substring(0, 8)}…
                      </span>
                    ) : (
                      <em>Unlinked</em>
                    )}
                  </td>
                  <td
                    style={{
                      fontSize: "0.875rem",
                      color: "var(--color-text-muted)",
                      maxWidth: 200,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {run.notes ?? "—"}
                  </td>
                  <td
                    style={{
                      fontSize: "0.875rem",
                      color: "var(--color-text-muted)",
                    }}
                  >
                    {formatDate(run.updated_at)}
                  </td>
                  <td>
                    <select
                      value={run.scenario_type}
                      onChange={(e) =>
                        handleScenarioTypeChange(
                          run.id,
                          e.target.value as FeasibilityScenarioType,
                        )
                      }
                      style={{
                        padding: "4px 8px",
                        border: "1px solid var(--color-border)",
                        borderRadius: 4,
                        fontSize: "0.8rem",
                        background: "var(--color-surface)",
                        cursor: "pointer",
                      }}
                      aria-label={`Change scenario type for ${run.scenario_name}`}
                    >
                      <option value="base">Base</option>
                      <option value="upside">Upside</option>
                      <option value="downside">Downside</option>
                      <option value="investor">Investor</option>
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create modal */}
      {showCreateModal && (
        <CreateRunModal
          onClose={() => setShowCreateModal(false)}
          onCreated={handleCreated}
        />
      )}
    </PageContainer>
  );
}
