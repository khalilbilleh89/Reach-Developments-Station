"use client";

/**
 * Scenarios page — exposes the Scenario Engine through a user-facing workspace.
 *
 * Views
 * -----
 *  1. List view     — all scenarios with KPI strip, create button, status filter
 *  2. Detail panel  — selected scenario: metadata, lifecycle controls (approve/archive)
 *  3. Duplicate     — inline modal to duplicate a scenario with new name/code
 *  4. Comparison    — side-by-side metadata comparison of selected scenarios
 *
 * Backend endpoints consumed (all at /api/v1/scenarios):
 *   POST   /scenarios
 *   GET    /scenarios
 *   PATCH  /scenarios/{id}
 *   POST   /scenarios/{id}/duplicate
 *   POST   /scenarios/{id}/approve
 *   POST   /scenarios/{id}/archive
 *   POST   /scenarios/compare
 *
 * PR-V6-02 — Scenario Workspace Frontend & Lifecycle Control
 * PR-V6-03 — Lifecycle Linking: land_id query-param filter, land/feasibility navigation
 */

import React, { useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { PageContainer } from "@/components/shell/PageContainer";
import { MetricCard } from "@/components/dashboard/MetricCard";
import {
  listScenarios,
  createScenario,
  duplicateScenario,
  approveScenario,
  archiveScenario,
  compareScenarios,
} from "@/lib/scenario-api";
import type {
  Scenario,
  ScenarioCompareItem,
  ScenarioCreate,
  ScenarioDuplicateRequest,
  ScenarioStatus,
} from "@/lib/scenario-types";
import styles from "@/styles/demo-shell.module.css";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function statusBadgeClass(status: ScenarioStatus): string {
  switch (status) {
    case "approved":
      return styles.badgeGreen;
    case "draft":
      return styles.badgeBlue;
    case "archived":
      return styles.badgeGray;
    default:
      return styles.badgeGray;
  }
}

function formatStatus(status: ScenarioStatus): string {
  switch (status) {
    case "draft":
      return "Draft";
    case "approved":
      return "Approved";
    case "archived":
      return "Archived";
    default:
      return status;
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
// Modal shell
// ---------------------------------------------------------------------------

interface ModalShellProps {
  title: string;
  dialogId: string;
  onClose: () => void;
  children: React.ReactNode;
  wide?: boolean;
}

function ModalShell({ title, dialogId, onClose, children, wide }: ModalShellProps) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby={dialogId}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.4)",
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "center",
        zIndex: 1000,
        overflowY: "auto",
        padding: "40px 16px",
      }}
    >
      <div
        style={{
          background: "var(--color-surface)",
          borderRadius: 12,
          padding: 32,
          width: wide ? 720 : 480,
          maxWidth: "100%",
          boxShadow: "0 20px 40px rgba(0,0,0,0.15)",
        }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: 24,
          }}
        >
          <h2
            id={dialogId}
            style={{ margin: 0, fontSize: "1.125rem", fontWeight: 600 }}
          >
            {title}
          </h2>
          <button
            type="button"
            aria-label="Close dialog"
            onClick={onClose}
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              fontSize: "1.25rem",
              color: "var(--color-text-muted)",
              lineHeight: 1,
              padding: "2px 6px",
            }}
          >
            ×
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Field helpers
// ---------------------------------------------------------------------------

interface FieldProps {
  id: string;
  label: string;
  required?: boolean;
  children: React.ReactNode;
}

function Field({ id, label, required, children }: FieldProps) {
  return (
    <div style={{ marginBottom: 16 }}>
      <label
        htmlFor={id}
        style={{ display: "block", marginBottom: 6, fontSize: "0.875rem", fontWeight: 500 }}
      >
        {label} {required && <span aria-hidden="true">*</span>}
      </label>
      {children}
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: "8px 12px",
  border: "1px solid var(--color-border)",
  borderRadius: 6,
  fontSize: "0.875rem",
  boxSizing: "border-box",
  background: "var(--color-surface)",
};

// ---------------------------------------------------------------------------
// Create scenario modal
// ---------------------------------------------------------------------------

interface CreateScenarioModalProps {
  onClose: () => void;
  onCreated: () => void;
  initialLandId?: string | null;
}

function CreateScenarioModal({ onClose, onCreated, initialLandId }: CreateScenarioModalProps) {
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!name.trim()) {
        setError("Scenario name is required.");
        return;
      }
      setSubmitting(true);
      setError(null);
      const data: ScenarioCreate = {
        name: name.trim(),
        code: code.trim() || null,
        notes: notes.trim() || null,
        land_id: initialLandId ?? null,
      };
      try {
        await createScenario(data);
        onCreated();
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Failed to create scenario.");
      } finally {
        setSubmitting(false);
      }
    },
    [name, code, notes, onCreated, initialLandId],
  );

  return (
    <ModalShell title="New Scenario" dialogId="create-scenario-dialog-title" onClose={onClose}>
      {initialLandId && (
        <p
          style={{
            margin: "0 0 16px",
            fontSize: "0.8rem",
            color: "var(--color-text-muted)",
            background: "var(--color-surface-muted, #f9fafb)",
            padding: "8px 12px",
            borderRadius: 6,
            border: "1px solid var(--color-border)",
          }}
          data-testid="create-scenario-land-context"
        >
          Linked to land parcel:{" "}
          <span style={{ fontFamily: "monospace" }}>
            {initialLandId.length > 12 ? initialLandId.substring(0, 12) + "…" : initialLandId}
          </span>
        </p>
      )}
      <form onSubmit={handleSubmit}>
        <Field id="create-scenario-name" label="Name" required>
          <input
            id="create-scenario-name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Marina Tower — Base Case"
            style={inputStyle}
            // eslint-disable-next-line jsx-a11y/no-autofocus
            autoFocus
          />
        </Field>
        <Field id="create-scenario-code" label="Code">
          <input
            id="create-scenario-code"
            type="text"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="e.g. MT-BASE-01"
            style={inputStyle}
          />
        </Field>
        <Field id="create-scenario-notes" label="Notes">
          <textarea
            id="create-scenario-notes"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Optional notes about this scenario…"
            rows={3}
            style={{ ...inputStyle, resize: "vertical" }}
          />
        </Field>
        {error && (
          <p role="alert" style={{ color: "var(--color-error, #dc2626)", fontSize: "0.875rem", margin: "0 0 16px" }}>
            {error}
          </p>
        )}
        <div style={{ display: "flex", gap: 12, justifyContent: "flex-end" }}>
          <button type="button" onClick={onClose} className={styles.btnOutline} disabled={submitting}>
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting}
            style={{
              padding: "8px 20px",
              background: "var(--color-primary, #2563eb)",
              color: "#fff",
              border: "none",
              borderRadius: 6,
              fontSize: "0.875rem",
              fontWeight: 500,
              cursor: submitting ? "not-allowed" : "pointer",
              opacity: submitting ? 0.7 : 1,
            }}
          >
            {submitting ? "Creating…" : "Create Scenario"}
          </button>
        </div>
      </form>
    </ModalShell>
  );
}

// ---------------------------------------------------------------------------
// Duplicate scenario modal
// ---------------------------------------------------------------------------

interface DuplicateScenarioModalProps {
  scenario: Scenario;
  onClose: () => void;
  onDuplicated: () => void;
}

function DuplicateScenarioModal({ scenario, onClose, onDuplicated }: DuplicateScenarioModalProps) {
  const [name, setName] = useState(`${scenario.name} (Copy)`);
  const [code, setCode] = useState("");
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!name.trim()) {
        setError("Scenario name is required.");
        return;
      }
      setSubmitting(true);
      setError(null);
      const data: ScenarioDuplicateRequest = {
        name: name.trim(),
        code: code.trim() || null,
        notes: notes.trim() || null,
      };
      try {
        await duplicateScenario(scenario.id, data);
        onDuplicated();
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Failed to duplicate scenario.");
      } finally {
        setSubmitting(false);
      }
    },
    [scenario.id, name, code, notes, onDuplicated],
  );

  return (
    <ModalShell title={`Duplicate: ${scenario.name}`} dialogId="duplicate-scenario-dialog-title" onClose={onClose}>
      <form onSubmit={handleSubmit}>
        <Field id="duplicate-scenario-name" label="New Name" required>
          <input
            id="duplicate-scenario-name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            style={inputStyle}
            // eslint-disable-next-line jsx-a11y/no-autofocus
            autoFocus
          />
        </Field>
        <Field id="duplicate-scenario-code" label="New Code">
          <input
            id="duplicate-scenario-code"
            type="text"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="Optional code override"
            style={inputStyle}
          />
        </Field>
        <Field id="duplicate-scenario-notes" label="Notes">
          <textarea
            id="duplicate-scenario-notes"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Optional notes for the duplicate…"
            rows={3}
            style={{ ...inputStyle, resize: "vertical" }}
          />
        </Field>
        {error && (
          <p role="alert" style={{ color: "var(--color-error, #dc2626)", fontSize: "0.875rem", margin: "0 0 16px" }}>
            {error}
          </p>
        )}
        <div style={{ display: "flex", gap: 12, justifyContent: "flex-end" }}>
          <button type="button" onClick={onClose} className={styles.btnOutline} disabled={submitting}>
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting}
            style={{
              padding: "8px 20px",
              background: "var(--color-primary, #2563eb)",
              color: "#fff",
              border: "none",
              borderRadius: 6,
              fontSize: "0.875rem",
              fontWeight: 500,
              cursor: submitting ? "not-allowed" : "pointer",
              opacity: submitting ? 0.7 : 1,
            }}
          >
            {submitting ? "Duplicating…" : "Duplicate Scenario"}
          </button>
        </div>
      </form>
    </ModalShell>
  );
}

// ---------------------------------------------------------------------------
// Comparison view
// ---------------------------------------------------------------------------

interface CompareViewProps {
  items: ScenarioCompareItem[];
  onClose: () => void;
}

function CompareView({ items, onClose }: CompareViewProps) {
  return (
    <ModalShell title="Scenario Comparison" dialogId="compare-scenarios-dialog-title" onClose={onClose} wide>
      <div style={{ overflowX: "auto" }}>
        <table
          className={styles.table}
          aria-label="Scenario comparison"
          style={{ width: "100%", tableLayout: "fixed" }}
        >
          <thead>
            <tr>
              <th scope="col" style={{ width: 180 }}>Field</th>
              {items.map((item) => (
                <th scope="col" key={item.scenario_id}>
                  {item.scenario_name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr>
              <td style={{ fontWeight: 500 }}>Status</td>
              {items.map((item) => {
                const badgeClass = statusBadgeClass(item.status);
                const label = formatStatus(item.status);
                return (
                  <td key={item.scenario_id}>
                    <span className={badgeClass || styles.badgeGray}>
                      {label}
                    </span>
                  </td>
                );
              })}
            </tr>
            <tr>
              <td style={{ fontWeight: 500 }}>Latest Version</td>
              {items.map((item) => (
                <td key={item.scenario_id}>
                  {item.latest_version_number !== null && item.latest_version_number !== undefined
                    ? `v${item.latest_version_number}`
                    : "—"}
                </td>
              ))}
            </tr>
            <tr>
              <td style={{ fontWeight: 500 }}>Assumptions</td>
              {items.map((item) => (
                <td key={item.scenario_id}>
                  {item.assumptions_json
                    ? Object.keys(item.assumptions_json).length > 0
                      ? `${Object.keys(item.assumptions_json).length} field(s)`
                      : "Empty"
                    : "—"}
                </td>
              ))}
            </tr>
            <tr>
              <td style={{ fontWeight: 500 }}>Comparison Metrics</td>
              {items.map((item) => (
                <td key={item.scenario_id}>
                  {item.comparison_metrics_json
                    ? Object.keys(item.comparison_metrics_json).length > 0
                      ? `${Object.keys(item.comparison_metrics_json).length} metric(s)`
                      : "Empty"
                    : "—"}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
      <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 24 }}>
        <button type="button" onClick={onClose} className={styles.btnOutline}>
          Close
        </button>
      </div>
    </ModalShell>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

type ViewMode = "list" | "detail";

export default function ScenariosPage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  // land_id and new=1 can be passed as query params from the Land page
  const landIdParam = searchParams.get("land_id") ?? null;
  const openNewParam = searchParams.get("new") === "1";

  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [viewMode, setViewMode] = useState<ViewMode>("list");
  const [selectedScenario, setSelectedScenario] = useState<Scenario | null>(null);

  const [statusFilter, setStatusFilter] = useState<ScenarioStatus | "">("");
  // landFilter is set from the query param on mount and can be cleared by the user
  const [landFilter, setLandFilter] = useState<string | null>(landIdParam);

  const [showCreate, setShowCreate] = useState(openNewParam);
  const [duplicateTarget, setDuplicateTarget] = useState<Scenario | null>(null);
  const [compareItems, setCompareItems] = useState<ScenarioCompareItem[] | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const [lifecycleError, setLifecycleError] = useState<string | null>(null);
  const [lifecyclePending, setLifecyclePending] = useState<string | null>(null);
  const [compareLoading, setCompareLoading] = useState(false);
  const [compareError, setCompareError] = useState<string | null>(null);

  // ---- Data loading -------------------------------------------------------

  const loadScenarios = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await listScenarios({
        status: statusFilter || undefined,
        land_id: landFilter ?? undefined,
        limit: 200,
      });
      setScenarios(result.items);
      setTotal(result.total);
      // Clear stale selections whenever the visible dataset changes so that
      // IDs removed by a filter change can no longer trigger Compare.
      setSelectedIds(new Set());
      setCompareItems(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load scenarios.");
    } finally {
      setLoading(false);
    }
  }, [statusFilter, landFilter]);

  useEffect(() => {
    loadScenarios();
  }, [loadScenarios]);

  // ---- Derived KPIs -------------------------------------------------------

  const draftCount = scenarios.filter((s) => s.status === "draft").length;
  const approvedCount = scenarios.filter((s) => s.status === "approved").length;
  const archivedCount = scenarios.filter((s) => s.status === "archived").length;

  // ---- Handlers -----------------------------------------------------------

  const handleSelectScenario = useCallback((scenario: Scenario) => {
    setSelectedScenario(scenario);
    setViewMode("detail");
    setLifecycleError(null);
  }, []);

  const handleBackToList = useCallback(() => {
    setViewMode("list");
    setSelectedScenario(null);
    setLifecycleError(null);
  }, []);

  const handleCreated = useCallback(() => {
    setShowCreate(false);
    loadScenarios();
  }, [loadScenarios]);

  const handleDuplicated = useCallback(() => {
    setDuplicateTarget(null);
    loadScenarios();
  }, [loadScenarios]);

  const handleApprove = useCallback(
    async (scenario: Scenario) => {
      setLifecyclePending(scenario.id);
      setLifecycleError(null);
      try {
        const updated = await approveScenario(scenario.id);
        setSelectedScenario(updated);
        setScenarios((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
      } catch (err: unknown) {
        setLifecycleError(err instanceof Error ? err.message : "Failed to approve scenario.");
      } finally {
        setLifecyclePending(null);
      }
    },
    [],
  );

  const handleArchive = useCallback(
    async (scenario: Scenario) => {
      setLifecyclePending(scenario.id);
      setLifecycleError(null);
      try {
        const updated = await archiveScenario(scenario.id);
        setSelectedScenario(updated);
        setScenarios((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
      } catch (err: unknown) {
        setLifecycleError(err instanceof Error ? err.message : "Failed to archive scenario.");
      } finally {
        setLifecyclePending(null);
      }
    },
    [],
  );

  const handleToggleSelect = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  const handleCompare = useCallback(async () => {
    if (selectedIds.size < 2) return;
    setCompareLoading(true);
    setCompareError(null);
    try {
      const result = await compareScenarios({ scenario_ids: Array.from(selectedIds) });
      setCompareItems(result.scenarios);
    } catch (err: unknown) {
      setCompareError(err instanceof Error ? err.message : "Failed to compare scenarios.");
    } finally {
      setCompareLoading(false);
    }
  }, [selectedIds]);

  // ---- Render helpers -----------------------------------------------------

  const renderListView = () => (
    <>
      {/* KPI strip */}
      <div className={styles.kpiGrid}>
        <MetricCard label="Total Scenarios" value={String(total)} trend="neutral" />
        <MetricCard label="Draft" value={String(draftCount)} trend="neutral" />
        <MetricCard label="Approved" value={String(approvedCount)} trend="positive" />
        <MetricCard label="Archived" value={String(archivedCount)} trend="neutral" />
      </div>

      {/* Land filter indicator */}
      {landFilter && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            marginBottom: 12,
            padding: "8px 14px",
            background: "#eff6ff",
            border: "1px solid #bfdbfe",
            borderRadius: 6,
            fontSize: "0.875rem",
          }}
          data-testid="land-filter-banner"
        >
          <span>
            Showing scenarios linked to land parcel:{" "}
            <span style={{ fontFamily: "monospace" }}>
              {landFilter.length > 12 ? landFilter.substring(0, 12) + "…" : landFilter}
            </span>
          </span>
          <button
            type="button"
            onClick={() => {
              setLandFilter(null);
              router.push("/scenarios");
            }}
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              color: "var(--color-primary, #2563eb)",
              fontSize: "0.8rem",
              textDecoration: "underline",
              padding: 0,
            }}
            aria-label="Clear land filter"
          >
            Clear filter
          </button>
          <button
            type="button"
            onClick={() => router.push(`/land`)}
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              color: "var(--color-primary, #2563eb)",
              fontSize: "0.8rem",
              textDecoration: "underline",
              padding: 0,
            }}
          >
            ← Back to Land
          </button>
        </div>
      )}

      {/* Toolbar */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 16,
          flexWrap: "wrap",
          gap: 12,
        }}
      >
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <label htmlFor="status-filter" style={{ fontSize: "0.875rem", fontWeight: 500 }}>
            Status:
          </label>
          <select
            id="status-filter"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as ScenarioStatus | "")}
            style={{ ...inputStyle, width: "auto" }}
          >
            <option value="">All</option>
            <option value="draft">Draft</option>
            <option value="approved">Approved</option>
            <option value="archived">Archived</option>
          </select>

          {selectedIds.size >= 2 && (
            <button
              type="button"
              onClick={handleCompare}
              disabled={compareLoading}
              style={{
                padding: "6px 14px",
                background: "var(--color-primary, #2563eb)",
                color: "#fff",
                border: "none",
                borderRadius: 6,
                fontSize: "0.875rem",
                cursor: compareLoading ? "not-allowed" : "pointer",
                opacity: compareLoading ? 0.7 : 1,
              }}
            >
              {compareLoading ? "Loading…" : `Compare (${selectedIds.size})`}
            </button>
          )}
          {compareError && (
            <span role="alert" style={{ color: "var(--color-error, #dc2626)", fontSize: "0.875rem" }}>
              {compareError}
            </span>
          )}
        </div>

        <button
          type="button"
          onClick={() => setShowCreate(true)}
          style={{
            padding: "8px 16px",
            background: "var(--color-primary, #2563eb)",
            color: "#fff",
            border: "none",
            borderRadius: 6,
            fontSize: "0.875rem",
            fontWeight: 500,
            cursor: "pointer",
          }}
        >
          + New Scenario
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className={styles.errorBanner} role="alert" style={{ marginBottom: 16 }}>
          {error}
        </div>
      )}

      {/* Table */}
      <div className={styles.tableWrapper}>
        {loading ? (
          <p style={{ padding: "24px 0", color: "var(--color-text-muted)", textAlign: "center" }}>
            Loading scenarios…
          </p>
        ) : scenarios.length === 0 ? (
          <p style={{ padding: "24px 0", color: "var(--color-text-muted)", textAlign: "center" }}>
            No scenarios found. Create the first one.
          </p>
        ) : (
          <table className={styles.table} aria-label="Scenarios list">
            <thead>
              <tr>
                <th scope="col" style={{ width: 36 }}>
                  <span
                    style={{
                      position: "absolute",
                      width: 1,
                      height: 1,
                      padding: 0,
                      margin: -1,
                      overflow: "hidden",
                      clip: "rect(0, 0, 0, 0)",
                      whiteSpace: "nowrap",
                      border: 0,
                    }}
                  >
                    Select
                  </span>
                </th>
                <th scope="col">Name</th>
                <th scope="col">Code</th>
                <th scope="col">Status</th>
                <th scope="col">Source Type</th>
                <th scope="col">Created</th>
                <th scope="col">Actions</th>
              </tr>
            </thead>
            <tbody>
              {scenarios.map((scenario) => (
                <tr key={scenario.id}>
                  <td>
                    <input
                      type="checkbox"
                      aria-label={`Select ${scenario.name}`}
                      checked={selectedIds.has(scenario.id)}
                      onChange={() => handleToggleSelect(scenario.id)}
                    />
                  </td>
                  <td>
                    <button
                      type="button"
                      onClick={() => handleSelectScenario(scenario)}
                      style={{
                        background: "none",
                        border: "none",
                        cursor: "pointer",
                        color: "var(--color-primary, #2563eb)",
                        fontWeight: 500,
                        padding: 0,
                        fontSize: "inherit",
                        textAlign: "left",
                      }}
                    >
                      {scenario.name}
                    </button>
                  </td>
                  <td className={styles.monospaceCell}>{scenario.code ?? "—"}</td>
                  <td>
                    <span className={statusBadgeClass(scenario.status)}>
                      {formatStatus(scenario.status)}
                    </span>
                  </td>
                  <td>{scenario.source_type}</td>
                  <td>{formatDate(scenario.created_at)}</td>
                  <td>
                    <div style={{ display: "flex", gap: 6 }}>
                      <button
                        type="button"
                        className={styles.btnOutline}
                        onClick={() => setDuplicateTarget(scenario)}
                        style={{ fontSize: "0.75rem", padding: "3px 10px" }}
                      >
                        Duplicate
                      </button>
                      <button
                        type="button"
                        className={styles.btnOutline}
                        onClick={() => handleSelectScenario(scenario)}
                        style={{ fontSize: "0.75rem", padding: "3px 10px" }}
                      >
                        View
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );

  const renderDetailView = () => {
    if (!selectedScenario) return null;
    const isPending = lifecyclePending === selectedScenario.id;

    return (
      <>
        {/* Back */}
        <button
          type="button"
          onClick={handleBackToList}
          className={styles.btnOutline}
          style={{ marginBottom: 24, display: "inline-flex", alignItems: "center", gap: 6 }}
        >
          ← Back to Scenarios
        </button>

        {/* Header */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            marginBottom: 24,
            flexWrap: "wrap",
            gap: 12,
          }}
        >
          <div>
            <h2 style={{ margin: "0 0 4px", fontSize: "1.25rem", fontWeight: 600 }}>
              {selectedScenario.name}
            </h2>
            {selectedScenario.code && (
              <span className={styles.monospaceCell} style={{ fontSize: "0.8rem", color: "var(--color-text-muted)" }}>
                {selectedScenario.code}
              </span>
            )}
          </div>
          <span className={statusBadgeClass(selectedScenario.status)}>
            {formatStatus(selectedScenario.status)}
          </span>
        </div>

        {/* Lifecycle error */}
        {lifecycleError && (
          <div className={styles.errorBanner} role="alert" style={{ marginBottom: 16 }}>
            {lifecycleError}
          </div>
        )}

        {/* Metadata grid */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
            gap: 16,
            marginBottom: 24,
            padding: 20,
            background: "var(--color-surface-muted, #f9fafb)",
            borderRadius: 8,
            border: "1px solid var(--color-border)",
          }}
        >
          <MetadataItem label="Source Type" value={selectedScenario.source_type} />
          <MetadataItem
            label="Base Scenario"
            value={selectedScenario.base_scenario_id ?? "—"}
          />
          <MetadataItem
            label="Project"
            value={selectedScenario.project_id ?? "—"}
          />
          <MetadataItem
            label="Land"
            value={selectedScenario.land_id ?? "—"}
          />
          <MetadataItem
            label="Active"
            value={selectedScenario.is_active ? "Yes" : "No"}
          />
          <MetadataItem label="Created" value={formatDate(selectedScenario.created_at)} />
          <MetadataItem label="Updated" value={formatDate(selectedScenario.updated_at)} />
        </div>

        {/* Notes */}
        {selectedScenario.notes && (
          <div
            style={{
              marginBottom: 24,
              padding: 16,
              background: "var(--color-surface-muted, #f9fafb)",
              borderRadius: 8,
              border: "1px solid var(--color-border)",
            }}
          >
            <p style={{ margin: 0, fontSize: "0.875rem", color: "var(--color-text-muted)" }}>
              <strong>Notes:</strong> {selectedScenario.notes}
            </p>
          </div>
        )}

        {/* Lifecycle actions */}
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 24 }}>
          {selectedScenario.status === "draft" && (
            <button
              type="button"
              disabled={isPending}
              onClick={() => handleApprove(selectedScenario)}
              style={{
                padding: "8px 20px",
                background: "#16a34a",
                color: "#fff",
                border: "none",
                borderRadius: 6,
                fontSize: "0.875rem",
                fontWeight: 500,
                cursor: isPending ? "not-allowed" : "pointer",
                opacity: isPending ? 0.7 : 1,
              }}
            >
              {isPending ? "Approving…" : "Approve"}
            </button>
          )}
          {selectedScenario.status !== "archived" && (
            <button
              type="button"
              disabled={isPending}
              onClick={() => handleArchive(selectedScenario)}
              className={styles.btnOutline}
              style={{ opacity: isPending ? 0.7 : 1 }}
            >
              {isPending ? "Archiving…" : "Archive"}
            </button>
          )}
          <button
            type="button"
            className={styles.btnOutline}
            onClick={() => setDuplicateTarget(selectedScenario)}
          >
            Duplicate
          </button>
        </div>

        {/* Lifecycle cross-links */}
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: 12,
            padding: "16px 20px",
            background: "var(--color-surface-muted, #f9fafb)",
            borderRadius: 8,
            border: "1px solid var(--color-border)",
          }}
          data-testid="scenario-lifecycle-links"
        >
          {/* Land origin — show navigation when land_id is present */}
          {selectedScenario.land_id ? (
            <button
              type="button"
              onClick={() =>
                router.push(
                  `/land`,
                )
              }
              style={{
                padding: "6px 14px",
                border: "1px solid var(--color-border)",
                borderRadius: 6,
                background: "var(--color-surface)",
                color: "var(--color-text)",
                cursor: "pointer",
                fontSize: "0.875rem",
              }}
              aria-label="Open land parcel"
              data-testid="scenario-open-land-btn"
            >
              ← Open Land
            </button>
          ) : (
            <span
              style={{ fontSize: "0.8rem", color: "var(--color-text-muted)", alignSelf: "center" }}
              data-testid="scenario-no-land-link"
            >
              No linked land parcel
            </span>
          )}

          {/* Feasibility — view existing runs or start a new run */}
          <button
            type="button"
            onClick={() =>
              router.push(
                `/feasibility?scenario_id=${encodeURIComponent(selectedScenario.id)}`,
              )
            }
            style={{
              padding: "6px 14px",
              border: "1px solid var(--color-border)",
              borderRadius: 6,
              background: "var(--color-surface)",
              color: "var(--color-text)",
              cursor: "pointer",
              fontSize: "0.875rem",
            }}
            aria-label="View feasibility runs for this scenario"
            data-testid="scenario-view-feasibility-btn"
          >
            View Feasibility Runs →
          </button>

          <button
            type="button"
            onClick={() =>
              router.push(
                `/feasibility?scenario_id=${encodeURIComponent(selectedScenario.id)}&new=1`,
              )
            }
            style={{
              padding: "6px 14px",
              border: "1px solid var(--color-primary, #2563eb)",
              borderRadius: 6,
              background: "var(--color-surface)",
              color: "var(--color-primary, #2563eb)",
              cursor: "pointer",
              fontSize: "0.875rem",
            }}
            aria-label="Run new feasibility for this scenario"
            data-testid="scenario-run-feasibility-btn"
          >
            + Run Feasibility →
          </button>
        </div>
      </>
    );
  };

  return (
    <PageContainer title="Scenarios">
      {viewMode === "list" && renderListView()}
      {viewMode === "detail" && renderDetailView()}

      {/* Modals */}
      {showCreate && (
        <CreateScenarioModal
          onClose={() => setShowCreate(false)}
          onCreated={handleCreated}
          initialLandId={landFilter}
        />
      )}
      {duplicateTarget && (
        <DuplicateScenarioModal
          scenario={duplicateTarget}
          onClose={() => setDuplicateTarget(null)}
          onDuplicated={handleDuplicated}
        />
      )}
      {compareItems && (
        <CompareView
          items={compareItems}
          onClose={() => {
            setCompareItems(null);
            setSelectedIds(new Set());
          }}
        />
      )}
    </PageContainer>
  );
}

// ---------------------------------------------------------------------------
// Metadata item helper
// ---------------------------------------------------------------------------

function MetadataItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p style={{ margin: "0 0 2px", fontSize: "0.75rem", color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
        {label}
      </p>
      <p style={{ margin: 0, fontSize: "0.875rem", fontWeight: 500 }}>
        {value}
      </p>
    </div>
  );
}
