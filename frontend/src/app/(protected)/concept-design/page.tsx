"use client";

/**
 * Concept Design page — exposes the existing Concept Design backend module
 * through a full user-facing workflow.
 *
 * Views
 * -----
 *  1. List view  — all concept options with KPI strip, create button
 *  2. Detail view — selected option: summary panel, unit-mix editor, promote action
 *  3. Comparison view — side-by-side option comparison filtered by project/scenario
 *
 * Backend endpoints consumed (all at /api/v1/concept-options):
 *   POST   /concept-options
 *   GET    /concept-options
 *   GET    /concept-options/compare
 *   GET    /concept-options/{id}
 *   PATCH  /concept-options/{id}
 *   POST   /concept-options/{id}/unit-mix
 *   GET    /concept-options/{id}/summary
 *   POST   /concept-options/{id}/promote
 *
 * PR-CONCEPT-055
 */

import React, { useCallback, useEffect, useState } from "react";
import { PageContainer } from "@/components/shell/PageContainer";
import { MetricCard } from "@/components/dashboard/MetricCard";
import {
  listConceptOptions,
  getConceptOptionSummary,
  createConceptOption,
  updateConceptOption,
  addConceptUnitMixLine,
  compareConceptOptions,
  promoteConceptOption,
} from "@/lib/concept-design-api";
import type {
  ConceptOption,
  ConceptOptionCreate,
  ConceptOptionStatus,
  ConceptOptionSummary,
  ConceptOptionComparisonResponse,
  ConceptUnitMixLineCreate,
  ConceptPromotionResponse,
} from "@/lib/concept-design-types";
import styles from "@/styles/demo-shell.module.css";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function statusBadgeClass(status: ConceptOptionStatus): string {
  switch (status) {
    case "active":
      return styles.badgeGreen;
    case "draft":
      return styles.badgeYellow;
    case "archived":
      return styles.badgeGray;
    default:
      return styles.badgeGray;
  }
}

function statusLabel(status: ConceptOptionStatus): string {
  switch (status) {
    case "active":
      return "Active";
    case "draft":
      return "Draft";
    case "archived":
      return "Archived";
    default:
      return status;
  }
}

function formatNum(value: number | null | undefined, decimals = 0): string {
  if (value == null) return "—";
  return value.toLocaleString(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

function formatPct(value: number | null | undefined): string {
  if (value == null) return "—";
  return `${(value * 100).toFixed(1)}%`;
}

// ---------------------------------------------------------------------------
// Shared modal wrapper
// ---------------------------------------------------------------------------

interface ModalWrapperProps {
  title: string;
  titleId: string;
  onClose: () => void;
  children: React.ReactNode;
}

function ModalWrapper({ title, titleId, onClose, children }: ModalWrapperProps) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.4)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1000,
        padding: "16px",
      }}
    >
      <div
        style={{
          background: "var(--color-surface)",
          borderRadius: 12,
          padding: 32,
          width: 520,
          maxWidth: "100%",
          maxHeight: "90vh",
          overflowY: "auto",
          boxShadow: "0 20px 40px rgba(0,0,0,0.15)",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: 24,
          }}
        >
          <h2
            id={titleId}
            style={{ margin: 0, fontSize: "1.125rem", fontWeight: 600 }}
          >
            {title}
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            style={{
              background: "none",
              border: "none",
              fontSize: "1.25rem",
              cursor: "pointer",
              color: "var(--color-text-muted)",
              lineHeight: 1,
            }}
          >
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Inline error alert
// ---------------------------------------------------------------------------

function ErrorAlert({ message }: { message: string }) {
  return (
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
      {message}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Shared form input helpers
// ---------------------------------------------------------------------------

interface FieldProps {
  label: string;
  id: string;
  required?: boolean;
  children: React.ReactNode;
}

function Field({ label, id, required, children }: FieldProps) {
  return (
    <div style={{ marginBottom: 16 }}>
      <label
        htmlFor={id}
        style={{
          display: "block",
          marginBottom: 6,
          fontSize: "0.875rem",
          fontWeight: 500,
        }}
      >
        {label}
        {required && (
          <span aria-hidden style={{ color: "#b91c1c", marginLeft: 2 }}>
            *
          </span>
        )}
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
  background: "var(--color-surface)",
  boxSizing: "border-box",
};

// ---------------------------------------------------------------------------
// Create / Edit concept option form modal
// ---------------------------------------------------------------------------

interface ConceptOptionFormModalProps {
  existing?: ConceptOption | null;
  onClose: () => void;
  onSaved: () => void;
}

function ConceptOptionFormModal({
  existing,
  onClose,
  onSaved,
}: ConceptOptionFormModalProps) {
  const isEdit = existing != null;

  const [name, setName] = useState(existing?.name ?? "");
  const [description, setDescription] = useState(existing?.description ?? "");
  const [status, setStatus] = useState<ConceptOptionStatus>(
    existing?.status ?? "draft",
  );
  const [projectId, setProjectId] = useState(existing?.project_id ?? "");
  const [scenarioId, setScenarioId] = useState(existing?.scenario_id ?? "");
  const [siteArea, setSiteArea] = useState(
    existing?.site_area != null ? String(existing.site_area) : "",
  );
  const [grossFloorArea, setGrossFloorArea] = useState(
    existing?.gross_floor_area != null ? String(existing.gross_floor_area) : "",
  );
  const [buildingCount, setBuildingCount] = useState(
    existing?.building_count != null ? String(existing.building_count) : "",
  );
  const [floorCount, setFloorCount] = useState(
    existing?.floor_count != null ? String(existing.floor_count) : "",
  );

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!name.trim()) {
        setError("Name is required.");
        return;
      }
      setSubmitting(true);
      setError(null);

      try {
        if (isEdit && existing) {
          await updateConceptOption(existing.id, {
            name: name.trim(),
            description: description.trim() || null,
            status,
            site_area: siteArea ? parseFloat(siteArea) : null,
            gross_floor_area: grossFloorArea ? parseFloat(grossFloorArea) : null,
            building_count: buildingCount ? parseInt(buildingCount, 10) : null,
            floor_count: floorCount ? parseInt(floorCount, 10) : null,
          });
        } else {
          const payload: ConceptOptionCreate = {
            name: name.trim(),
            description: description.trim() || null,
            status,
            project_id: projectId.trim() || null,
            scenario_id: scenarioId.trim() || null,
            site_area: siteArea ? parseFloat(siteArea) : null,
            gross_floor_area: grossFloorArea ? parseFloat(grossFloorArea) : null,
            building_count: buildingCount ? parseInt(buildingCount, 10) : null,
            floor_count: floorCount ? parseInt(floorCount, 10) : null,
          };
          await createConceptOption(payload);
        }
        onSaved();
      } catch (err: unknown) {
        setError(
          err instanceof Error
            ? err.message
            : `Failed to ${isEdit ? "update" : "create"} concept option.`,
        );
      } finally {
        setSubmitting(false);
      }
    },
    [
      name,
      description,
      status,
      projectId,
      scenarioId,
      siteArea,
      grossFloorArea,
      buildingCount,
      floorCount,
      isEdit,
      existing,
      onSaved,
    ],
  );

  return (
    <ModalWrapper
      title={isEdit ? "Edit Concept Option" : "New Concept Option"}
      titleId="concept-option-form-title"
      onClose={onClose}
    >
      {error && <ErrorAlert message={error} />}
      <form onSubmit={handleSubmit}>
        <Field label="Name" id="co-name" required>
          <input
            id="co-name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            style={inputStyle}
            maxLength={255}
          />
        </Field>

        <Field label="Status" id="co-status">
          <select
            id="co-status"
            value={status}
            onChange={(e) => setStatus(e.target.value as ConceptOptionStatus)}
            style={inputStyle}
          >
            <option value="draft">Draft</option>
            <option value="active">Active</option>
            <option value="archived">Archived</option>
          </select>
        </Field>

        <Field label="Description" id="co-description">
          <textarea
            id="co-description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={2}
            style={{ ...inputStyle, resize: "vertical" }}
          />
        </Field>

        {!isEdit && (
          <>
            <Field label="Project ID" id="co-project-id">
              <input
                id="co-project-id"
                type="text"
                value={projectId}
                onChange={(e) => setProjectId(e.target.value)}
                style={inputStyle}
                placeholder="Optional — leave blank to create unlinked"
              />
            </Field>

            <Field label="Scenario ID" id="co-scenario-id">
              <input
                id="co-scenario-id"
                type="text"
                value={scenarioId}
                onChange={(e) => setScenarioId(e.target.value)}
                style={inputStyle}
                placeholder="Optional"
              />
            </Field>
          </>
        )}

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <Field label="Site Area (m²)" id="co-site-area">
            <input
              id="co-site-area"
              type="number"
              min="0.01"
              step="any"
              value={siteArea}
              onChange={(e) => setSiteArea(e.target.value)}
              style={inputStyle}
            />
          </Field>
          <Field label="Gross Floor Area (m²)" id="co-gfa">
            <input
              id="co-gfa"
              type="number"
              min="0.01"
              step="any"
              value={grossFloorArea}
              onChange={(e) => setGrossFloorArea(e.target.value)}
              style={inputStyle}
            />
          </Field>
          <Field label="Buildings" id="co-buildings">
            <input
              id="co-buildings"
              type="number"
              min="1"
              step="1"
              value={buildingCount}
              onChange={(e) => setBuildingCount(e.target.value)}
              style={inputStyle}
            />
          </Field>
          <Field label="Floors" id="co-floors">
            <input
              id="co-floors"
              type="number"
              min="1"
              step="1"
              value={floorCount}
              onChange={(e) => setFloorCount(e.target.value)}
              style={inputStyle}
            />
          </Field>
        </div>

        <div style={{ display: "flex", justifyContent: "flex-end", gap: 12, marginTop: 8 }}>
          <button
            type="button"
            onClick={onClose}
            style={{
              padding: "8px 20px",
              border: "1px solid var(--color-border)",
              borderRadius: 6,
              background: "var(--color-surface)",
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
            {submitting
              ? isEdit
                ? "Saving…"
                : "Creating…"
              : isEdit
                ? "Save Changes"
                : "Create Option"}
          </button>
        </div>
      </form>
    </ModalWrapper>
  );
}

// ---------------------------------------------------------------------------
// Add unit-mix line modal
// ---------------------------------------------------------------------------

interface AddUnitMixModalProps {
  conceptOptionId: string;
  onClose: () => void;
  onAdded: () => void;
}

function AddUnitMixModal({
  conceptOptionId,
  onClose,
  onAdded,
}: AddUnitMixModalProps) {
  const [unitType, setUnitType] = useState("");
  const [unitsCount, setUnitsCount] = useState("");
  const [avgInternalArea, setAvgInternalArea] = useState("");
  const [avgSellableArea, setAvgSellableArea] = useState("");
  const [mixPct, setMixPct] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!unitType.trim()) {
        setError("Unit type is required.");
        return;
      }
      const count = parseInt(unitsCount, 10);
      if (!unitsCount || isNaN(count) || count < 1) {
        setError("Units count must be a positive integer.");
        return;
      }
      setSubmitting(true);
      setError(null);

      const payload: ConceptUnitMixLineCreate = {
        unit_type: unitType.trim(),
        units_count: count,
        avg_internal_area: avgInternalArea ? parseFloat(avgInternalArea) : null,
        avg_sellable_area: avgSellableArea ? parseFloat(avgSellableArea) : null,
        mix_percentage: mixPct ? parseFloat(mixPct) : null,
      };

      try {
        await addConceptUnitMixLine(conceptOptionId, payload);
        onAdded();
      } catch (err: unknown) {
        setError(
          err instanceof Error ? err.message : "Failed to add unit mix line.",
        );
      } finally {
        setSubmitting(false);
      }
    },
    [conceptOptionId, unitType, unitsCount, avgInternalArea, avgSellableArea, mixPct, onAdded],
  );

  return (
    <ModalWrapper
      title="Add Unit Mix Line"
      titleId="add-mix-title"
      onClose={onClose}
    >
      {error && <ErrorAlert message={error} />}
      <form onSubmit={handleSubmit}>
        <Field label="Unit Type" id="mix-type" required>
          <input
            id="mix-type"
            type="text"
            value={unitType}
            onChange={(e) => setUnitType(e.target.value)}
            style={inputStyle}
            placeholder="e.g. 1BR, 2BR, Studio"
            maxLength={100}
          />
        </Field>

        <Field label="Units Count" id="mix-count" required>
          <input
            id="mix-count"
            type="number"
            min="1"
            step="1"
            value={unitsCount}
            onChange={(e) => setUnitsCount(e.target.value)}
            style={inputStyle}
          />
        </Field>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <Field label="Avg Internal Area (m²)" id="mix-internal">
            <input
              id="mix-internal"
              type="number"
              min="0.01"
              step="any"
              value={avgInternalArea}
              onChange={(e) => setAvgInternalArea(e.target.value)}
              style={inputStyle}
            />
          </Field>
          <Field label="Avg Sellable Area (m²)" id="mix-sellable">
            <input
              id="mix-sellable"
              type="number"
              min="0.01"
              step="any"
              value={avgSellableArea}
              onChange={(e) => setAvgSellableArea(e.target.value)}
              style={inputStyle}
            />
          </Field>
        </div>

        <Field label="Mix %" id="mix-pct">
          <input
            id="mix-pct"
            type="number"
            min="0"
            max="100"
            step="any"
            value={mixPct}
            onChange={(e) => setMixPct(e.target.value)}
            style={inputStyle}
            placeholder="0–100"
          />
        </Field>

        <div style={{ display: "flex", justifyContent: "flex-end", gap: 12, marginTop: 8 }}>
          <button
            type="button"
            onClick={onClose}
            style={{
              padding: "8px 20px",
              border: "1px solid var(--color-border)",
              borderRadius: 6,
              background: "var(--color-surface)",
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
            {submitting ? "Adding…" : "Add Line"}
          </button>
        </div>
      </form>
    </ModalWrapper>
  );
}

// ---------------------------------------------------------------------------
// Promote concept option modal
// ---------------------------------------------------------------------------

interface PromoteModalProps {
  conceptOption: ConceptOption;
  onClose: () => void;
  onPromoted: () => void;
}

function PromoteModal({ conceptOption, onClose, onPromoted }: PromoteModalProps) {
  const [targetProjectId, setTargetProjectId] = useState(
    conceptOption.project_id ?? "",
  );
  const [phaseName, setPhaseName] = useState("");
  const [promotionNotes, setPromotionNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ConceptPromotionResponse | null>(null);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      setSubmitting(true);
      setError(null);

      try {
        const res = await promoteConceptOption(conceptOption.id, {
          target_project_id: targetProjectId.trim() || null,
          phase_name: phaseName.trim() || null,
          promotion_notes: promotionNotes.trim() || null,
        });
        setResult(res);
        onPromoted();
      } catch (err: unknown) {
        setError(
          err instanceof Error ? err.message : "Promotion failed.",
        );
      } finally {
        setSubmitting(false);
      }
    },
    [conceptOption.id, targetProjectId, phaseName, promotionNotes, onPromoted],
  );

  if (result) {
    return (
      <ModalWrapper
        title="Concept Promoted"
        titleId="promote-success-title"
        onClose={onClose}
      >
        <div
          style={{
            padding: "16px",
            background: "#dcfce7",
            border: "1px solid #86efac",
            borderRadius: 8,
            marginBottom: 16,
          }}
        >
          <p style={{ margin: 0, fontWeight: 600, color: "#15803d" }}>
            ✓ Promotion successful
          </p>
        </div>
        <dl
          style={{
            display: "grid",
            gridTemplateColumns: "auto 1fr",
            gap: "8px 16px",
            fontSize: "0.875rem",
            margin: 0,
          }}
        >
          <dt style={{ color: "var(--color-text-muted)", fontWeight: 500 }}>Phase</dt>
          <dd style={{ margin: 0 }}>{result.promoted_phase_name}</dd>
          <dt style={{ color: "var(--color-text-muted)", fontWeight: 500 }}>Project ID</dt>
          <dd style={{ margin: 0, fontFamily: "monospace", fontSize: "0.8rem" }}>
            {result.promoted_project_id}
          </dd>
          <dt style={{ color: "var(--color-text-muted)", fontWeight: 500 }}>Promoted At</dt>
          <dd style={{ margin: 0 }}>{formatDate(result.promoted_at)}</dd>
        </dl>
        <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 24 }}>
          <button
            type="button"
            onClick={onClose}
            style={{
              padding: "8px 20px",
              border: "none",
              borderRadius: 6,
              background: "var(--color-primary, #2563eb)",
              color: "#fff",
              cursor: "pointer",
              fontSize: "0.875rem",
            }}
          >
            Close
          </button>
        </div>
      </ModalWrapper>
    );
  }

  return (
    <ModalWrapper
      title="Promote Concept Option"
      titleId="promote-modal-title"
      onClose={onClose}
    >
      <p
        style={{
          fontSize: "0.875rem",
          color: "var(--color-text-muted)",
          marginTop: 0,
          marginBottom: 20,
        }}
      >
        Promoting <strong>{conceptOption.name}</strong> will create a project
        phase linked to this concept option. The option must be in{" "}
        <em>draft</em> or <em>active</em> status, have building and floor counts
        set, and contain at least one unit mix line.
      </p>

      {error && <ErrorAlert message={error} />}

      <form onSubmit={handleSubmit}>
        {!conceptOption.project_id && (
          <Field label="Target Project ID" id="promote-project" required>
            <input
              id="promote-project"
              type="text"
              value={targetProjectId}
              onChange={(e) => setTargetProjectId(e.target.value)}
              style={inputStyle}
              placeholder="Project to promote into"
            />
          </Field>
        )}

        <Field label="Phase Name (optional)" id="promote-phase">
          <input
            id="promote-phase"
            type="text"
            value={phaseName}
            onChange={(e) => setPhaseName(e.target.value)}
            style={inputStyle}
            placeholder="Leave blank to use a generated name"
            maxLength={255}
          />
        </Field>

        <Field label="Promotion Notes (optional)" id="promote-notes">
          <textarea
            id="promote-notes"
            value={promotionNotes}
            onChange={(e) => setPromotionNotes(e.target.value)}
            rows={2}
            style={{ ...inputStyle, resize: "vertical" }}
          />
        </Field>

        <div style={{ display: "flex", justifyContent: "flex-end", gap: 12, marginTop: 8 }}>
          <button
            type="button"
            onClick={onClose}
            style={{
              padding: "8px 20px",
              border: "1px solid var(--color-border)",
              borderRadius: 6,
              background: "var(--color-surface)",
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
              background: "#15803d",
              color: "#fff",
              cursor: submitting ? "not-allowed" : "pointer",
              fontSize: "0.875rem",
              fontWeight: 500,
            }}
          >
            {submitting ? "Promoting…" : "Promote Option"}
          </button>
        </div>
      </form>
    </ModalWrapper>
  );
}

// ---------------------------------------------------------------------------
// Summary panel — displays derived metrics from backend engine
// ---------------------------------------------------------------------------

interface SummaryPanelProps {
  optionId: string;
  onAddMixLine: () => void;
}

function SummaryPanel({ optionId, onAddMixLine }: SummaryPanelProps) {
  const [summary, setSummary] = useState<ConceptOptionSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSummary = useCallback(() => {
    setLoading(true);
    getConceptOptionSummary(optionId)
      .then((data) => {
        setSummary(data);
        setError(null);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Failed to load summary.");
        setSummary(null);
      })
      .finally(() => setLoading(false));
  }, [optionId]);

  useEffect(() => {
    fetchSummary();
  }, [fetchSummary]);

  if (loading) {
    return (
      <p style={{ color: "var(--color-text-muted)", fontSize: "0.875rem" }}>
        Loading summary…
      </p>
    );
  }

  if (error) {
    return <ErrorAlert message={error} />;
  }

  if (!summary) return null;

  return (
    <div>
      {/* Derived KPIs */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, marginBottom: 24 }}>
        {[
          { label: "Unit Count", value: String(summary.unit_count) },
          { label: "Sellable Area (m²)", value: formatNum(summary.sellable_area, 1) },
          { label: "Efficiency Ratio", value: formatPct(summary.efficiency_ratio) },
          { label: "Avg Unit Area (m²)", value: formatNum(summary.average_unit_area, 1) },
          { label: "Buildings", value: formatNum(summary.building_count) },
          { label: "Floors", value: formatNum(summary.floor_count) },
        ].map(({ label, value }) => (
          <div
            key={label}
            style={{
              background: "#f8fafc",
              border: "1px solid var(--color-border)",
              borderRadius: 8,
              padding: "12px 16px",
            }}
          >
            <div style={{ fontSize: "0.75rem", color: "var(--color-text-muted)", marginBottom: 4 }}>
              {label}
            </div>
            <div style={{ fontSize: "1.125rem", fontWeight: 600 }}>{value}</div>
          </div>
        ))}
      </div>

      {/* Unit mix table */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 8,
        }}
      >
        <h3 style={{ margin: 0, fontSize: "0.875rem", fontWeight: 600 }}>
          Unit Mix ({summary.mix_lines.length} line{summary.mix_lines.length !== 1 ? "s" : ""})
        </h3>
        <button
          type="button"
          onClick={onAddMixLine}
          style={{
            padding: "4px 12px",
            border: "1px solid var(--color-primary, #2563eb)",
            borderRadius: 6,
            background: "var(--color-surface)",
            color: "var(--color-primary, #2563eb)",
            cursor: "pointer",
            fontSize: "0.8rem",
            fontWeight: 500,
          }}
        >
          + Add Line
        </button>
      </div>

      {summary.mix_lines.length === 0 ? (
        <p
          style={{
            fontSize: "0.875rem",
            color: "var(--color-text-muted)",
            fontStyle: "italic",
          }}
        >
          No unit mix lines yet. Add at least one before promoting.
        </p>
      ) : (
        <div className={styles.tableWrapper}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Unit Type</th>
                <th>Count</th>
                <th>Avg Internal (m²)</th>
                <th>Avg Sellable (m²)</th>
                <th>Mix %</th>
              </tr>
            </thead>
            <tbody>
              {summary.mix_lines.map((line) => (
                <tr key={line.id}>
                  <td style={{ fontWeight: 500 }}>{line.unit_type}</td>
                  <td>{line.units_count}</td>
                  <td>{formatNum(line.avg_internal_area, 1)}</td>
                  <td>{formatNum(line.avg_sellable_area, 1)}</td>
                  <td>{line.mix_percentage != null ? `${line.mix_percentage}%` : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Detail view — selected option
// ---------------------------------------------------------------------------

interface DetailViewProps {
  option: ConceptOption;
  onBack: () => void;
  onEdit: (option: ConceptOption) => void;
  onRefresh: () => void;
}

function DetailView({ option, onBack, onEdit, onRefresh }: DetailViewProps) {
  const [showAddMix, setShowAddMix] = useState(false);
  const [showPromote, setShowPromote] = useState(false);
  const [summaryKey, setSummaryKey] = useState(0);

  const handleMixAdded = useCallback(() => {
    setShowAddMix(false);
    setSummaryKey((k) => k + 1);
  }, []);

  const handlePromoted = useCallback(() => {
    onRefresh();
  }, [onRefresh]);

  return (
    <div>
      {/* Back + toolbar */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 24,
          gap: 12,
          flexWrap: "wrap",
        }}
      >
        <button
          type="button"
          onClick={onBack}
          style={{
            background: "none",
            border: "none",
            color: "var(--color-primary, #2563eb)",
            cursor: "pointer",
            fontSize: "0.875rem",
            fontWeight: 500,
            display: "flex",
            alignItems: "center",
            gap: 4,
            padding: 0,
          }}
        >
          ← All Options
        </button>

        <div style={{ display: "flex", gap: 8 }}>
          <button
            type="button"
            onClick={() => onEdit(option)}
            style={{
              padding: "6px 16px",
              border: "1px solid var(--color-border)",
              borderRadius: 6,
              background: "var(--color-surface)",
              cursor: "pointer",
              fontSize: "0.875rem",
            }}
          >
            Edit
          </button>
          {!option.is_promoted && (
            <button
              type="button"
              onClick={() => setShowPromote(true)}
              style={{
                padding: "6px 16px",
                border: "none",
                borderRadius: 6,
                background: "#15803d",
                color: "#fff",
                cursor: "pointer",
                fontSize: "0.875rem",
                fontWeight: 500,
              }}
            >
              Promote →
            </button>
          )}
          {option.is_promoted && (
            <span
              className={`${styles.badge} ${styles.badgeGreen}`}
              style={{ padding: "6px 12px" }}
            >
              ✓ Promoted
            </span>
          )}
        </div>
      </div>

      {/* Option header */}
      <div
        style={{
          background: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          borderRadius: 8,
          padding: "20px 24px",
          marginBottom: 24,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "space-between",
            gap: 12,
          }}
        >
          <div>
            <h2 style={{ margin: "0 0 4px", fontSize: "1.25rem", fontWeight: 700 }}>
              {option.name}
            </h2>
            {option.description && (
              <p style={{ margin: "0 0 12px", fontSize: "0.875rem", color: "var(--color-text-muted)" }}>
                {option.description}
              </p>
            )}
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <span className={`${styles.badge} ${statusBadgeClass(option.status)}`}>
                {statusLabel(option.status)}
              </span>
              {option.project_id && (
                <span
                  className={`${styles.badge} ${styles.badgeBlue}`}
                  title={option.project_id}
                >
                  Project: {option.project_id.substring(0, 8)}…
                </span>
              )}
              {option.scenario_id && (
                <span
                  className={`${styles.badge} ${styles.badgePurple}`}
                  title={option.scenario_id}
                >
                  Scenario: {option.scenario_id.substring(0, 8)}…
                </span>
              )}
            </div>
          </div>
          <div style={{ fontSize: "0.8rem", color: "var(--color-text-muted)", textAlign: "right" }}>
            <div>Created {formatDate(option.created_at)}</div>
            <div>Updated {formatDate(option.updated_at)}</div>
          </div>
        </div>
      </div>

      {/* Summary panel (live from backend engine) */}
      <div
        style={{
          background: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          borderRadius: 8,
          padding: "20px 24px",
        }}
      >
        <h3 style={{ margin: "0 0 16px", fontSize: "1rem", fontWeight: 600 }}>
          Program Summary
        </h3>
        {/* key forces re-mount and re-fetch after mix line added */}
        <SummaryPanel
          key={summaryKey}
          optionId={option.id}
          onAddMixLine={() => setShowAddMix(true)}
        />
      </div>

      {showAddMix && (
        <AddUnitMixModal
          conceptOptionId={option.id}
          onClose={() => setShowAddMix(false)}
          onAdded={handleMixAdded}
        />
      )}

      {showPromote && (
        <PromoteModal
          conceptOption={option}
          onClose={() => setShowPromote(false)}
          onPromoted={handlePromoted}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Comparison view
// ---------------------------------------------------------------------------

function ComparisonView() {
  const [filterType, setFilterType] = useState<"project_id" | "scenario_id">("project_id");
  const [filterId, setFilterId] = useState("");
  const [comparison, setComparison] = useState<ConceptOptionComparisonResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCompare = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      if (!filterId.trim()) {
        setError("Please enter an ID to compare options.");
        return;
      }
      setLoading(true);
      setError(null);

      const params =
        filterType === "project_id"
          ? { project_id: filterId.trim() }
          : { scenario_id: filterId.trim() };

      compareConceptOptions(params)
        .then((data) => {
          setComparison(data);
        })
        .catch((err: unknown) => {
          setError(err instanceof Error ? err.message : "Comparison failed.");
          setComparison(null);
        })
        .finally(() => setLoading(false));
    },
    [filterType, filterId],
  );

  return (
    <div>
      <h2 style={{ margin: "0 0 16px", fontSize: "1rem", fontWeight: 600 }}>
        Compare Concept Options
      </h2>
      <p style={{ margin: "0 0 20px", fontSize: "0.875rem", color: "var(--color-text-muted)" }}>
        Select all options for a project or scenario and compare them side by
        side. Provide exactly one of: Project ID or Scenario ID.
      </p>

      <form onSubmit={handleCompare} style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 24 }}>
        <select
          value={filterType}
          onChange={(e) => setFilterType(e.target.value as "project_id" | "scenario_id")}
          style={{ ...inputStyle, width: "auto", minWidth: 160 }}
          aria-label="Filter type"
        >
          <option value="project_id">Project ID</option>
          <option value="scenario_id">Scenario ID</option>
        </select>
        <input
          type="text"
          value={filterId}
          onChange={(e) => setFilterId(e.target.value)}
          placeholder={filterType === "project_id" ? "Enter project ID" : "Enter scenario ID"}
          style={{ ...inputStyle, width: 300 }}
          aria-label="Filter ID"
        />
        <button
          type="submit"
          disabled={loading}
          style={{
            padding: "8px 20px",
            border: "none",
            borderRadius: 6,
            background: "var(--color-primary, #2563eb)",
            color: "#fff",
            cursor: loading ? "not-allowed" : "pointer",
            fontSize: "0.875rem",
            fontWeight: 500,
          }}
        >
          {loading ? "Comparing…" : "Compare"}
        </button>
      </form>

      {error && <ErrorAlert message={error} />}

      {comparison && (
        <div>
          <p style={{ fontSize: "0.875rem", color: "var(--color-text-muted)", marginBottom: 12 }}>
            Comparing <strong>{comparison.option_count}</strong> options by{" "}
            <strong>{comparison.comparison_basis}</strong>
          </p>
          <div className={styles.tableWrapper}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Option</th>
                  <th>Status</th>
                  <th>Units</th>
                  <th>Sellable (m²)</th>
                  <th>Efficiency</th>
                  <th>Avg Unit (m²)</th>
                  <th>Buildings</th>
                  <th>Floors</th>
                </tr>
              </thead>
              <tbody>
                {comparison.rows.map((row) => (
                  <tr
                    key={row.concept_option_id}
                    style={
                      row.is_best_sellable_area || row.is_best_efficiency || row.is_best_unit_count
                        ? { background: "#f0fdf4" }
                        : undefined
                    }
                  >
                    <td>
                      <div style={{ fontWeight: 500 }}>
                        {row.name}
                        {(row.is_best_sellable_area || row.is_best_efficiency || row.is_best_unit_count) && (
                          <span
                            className={`${styles.badge} ${styles.badgeGreen}`}
                            style={{ marginLeft: 8 }}
                          >
                            Best
                          </span>
                        )}
                      </div>
                    </td>
                    <td>
                      <span className={`${styles.badge} ${statusBadgeClass(row.status)}`}>
                        {statusLabel(row.status)}
                      </span>
                    </td>
                    <td>
                      {row.unit_count}
                      {row.is_best_unit_count && (
                        <span style={{ marginLeft: 4, color: "#15803d" }}>★</span>
                      )}
                    </td>
                    <td>
                      {formatNum(row.sellable_area, 1)}
                      {row.is_best_sellable_area && (
                        <span style={{ marginLeft: 4, color: "#15803d" }}>★</span>
                      )}
                    </td>
                    <td>
                      {formatPct(row.efficiency_ratio)}
                      {row.is_best_efficiency && (
                        <span style={{ marginLeft: 4, color: "#15803d" }}>★</span>
                      )}
                    </td>
                    <td>{formatNum(row.average_unit_area, 1)}</td>
                    <td>{formatNum(row.building_count)}</td>
                    <td>{formatNum(row.floor_count)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Options list — main view
// ---------------------------------------------------------------------------

type View = "list" | "detail" | "compare";

interface OptionsListProps {
  options: ConceptOption[];
  onSelectOption: (option: ConceptOption) => void;
  onEditOption: (option: ConceptOption) => void;
}

function OptionsList({ options, onSelectOption, onEditOption }: OptionsListProps) {
  return (
    <div className={styles.tableWrapper}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>Name</th>
            <th>Status</th>
            <th>Site Area (m²)</th>
            <th>GFA (m²)</th>
            <th>Buildings</th>
            <th>Floors</th>
            <th>Promoted</th>
            <th>Updated</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {options.map((opt) => (
            <tr
              key={opt.id}
              style={{ cursor: "pointer" }}
              onClick={() => onSelectOption(opt)}
            >
              <td style={{ fontWeight: 500 }}>{opt.name}</td>
              <td>
                <span className={`${styles.badge} ${statusBadgeClass(opt.status)}`}>
                  {statusLabel(opt.status)}
                </span>
              </td>
              <td>{formatNum(opt.site_area, 0)}</td>
              <td>{formatNum(opt.gross_floor_area, 0)}</td>
              <td>{opt.building_count ?? "—"}</td>
              <td>{opt.floor_count ?? "—"}</td>
              <td>
                {opt.is_promoted ? (
                  <span className={`${styles.badge} ${styles.badgeGreen}`}>✓ Yes</span>
                ) : (
                  <span className={`${styles.badge} ${styles.badgeGray}`}>No</span>
                )}
              </td>
              <td style={{ fontSize: "0.8rem", color: "var(--color-text-muted)" }}>
                {formatDate(opt.updated_at)}
              </td>
              <td onClick={(e) => e.stopPropagation()}>
                <button
                  type="button"
                  onClick={() => onEditOption(opt)}
                  style={{
                    padding: "3px 10px",
                    border: "1px solid var(--color-border)",
                    borderRadius: 4,
                    background: "var(--color-surface)",
                    cursor: "pointer",
                    fontSize: "0.8rem",
                  }}
                >
                  Edit
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page component
// ---------------------------------------------------------------------------

/**
 * Concept Design page — exposes the existing Concept Design backend
 * through a full user-facing workflow.
 */
export default function ConceptDesignPage() {
  const [view, setView] = useState<View>("list");
  const [options, setOptions] = useState<ConceptOption[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedOption, setSelectedOption] = useState<ConceptOption | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingOption, setEditingOption] = useState<ConceptOption | null>(null);

  const fetchOptions = useCallback(() => {
    setLoading(true);
    listConceptOptions({ limit: 100 })
      .then((resp) => {
        setOptions(resp.items);
        setTotal(resp.items.length);
        setError(null);
      })
      .catch((err: unknown) => {
        setError(
          err instanceof Error ? err.message : "Failed to load concept options.",
        );
        setOptions([]);
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    fetchOptions();
  }, [fetchOptions]);

  const handleSelectOption = useCallback((opt: ConceptOption) => {
    setSelectedOption(opt);
    setView("detail");
  }, []);

  const handleEditOption = useCallback((opt: ConceptOption) => {
    setEditingOption(opt);
  }, []);

  const handleSaved = useCallback(() => {
    setShowCreateModal(false);
    setEditingOption(null);
    fetchOptions();
  }, [fetchOptions]);

  const handleDetailRefresh = useCallback(() => {
    fetchOptions();
    // Re-fetch the selected option to reflect promoted status
    if (selectedOption) {
      listConceptOptions({ limit: 100 }).then((resp) => {
        const updated = resp.items.find((o) => o.id === selectedOption.id);
        if (updated) setSelectedOption(updated);
      });
    }
  }, [fetchOptions, selectedOption]);

  const handleBack = useCallback(() => {
    setSelectedOption(null);
    setView("list");
  }, []);

  // KPI counts
  const draftCount = options.filter((o) => o.status === "draft").length;
  const activeCount = options.filter((o) => o.status === "active").length;
  const promotedCount = options.filter((o) => o.is_promoted).length;

  return (
    <PageContainer
      title="Concept Design"
      subtitle="Create, compare, and promote concept design options for your development programme."
    >
      {/* KPI strip */}
      <div className={styles.kpiGrid}>
        <MetricCard title="Total Options" value={String(total)} />
        <MetricCard title="Draft" value={String(draftCount)} />
        <MetricCard title="Active" value={String(activeCount)} />
        <MetricCard title="Promoted" value={String(promotedCount)} />
      </div>

      {/* View tabs (only visible on list view) */}
      {view === "list" && (
        <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
          {(
            [
              { key: "list", label: "Options" },
              { key: "compare", label: "Compare" },
            ] as const
          ).map(({ key, label }) => (
            <button
              key={key}
              type="button"
              onClick={() => setView(key as View)}
              style={{
                padding: "6px 16px",
                border: "none",
                borderRadius: 6,
                cursor: "pointer",
                fontSize: "0.875rem",
                fontWeight: 500,
                background: view === key ? "var(--color-primary, #2563eb)" : "var(--color-surface)",
                color: view === key ? "#fff" : "var(--color-text)",
                borderBottom: view === key ? "none" : "1px solid var(--color-border)",
              }}
            >
              {label}
            </button>
          ))}
        </div>
      )}

      {/* Compare view shortcut button */}
      {view === "compare" && (
        <div style={{ marginBottom: 16 }}>
          <button
            type="button"
            onClick={() => setView("list")}
            style={{
              background: "none",
              border: "none",
              color: "var(--color-primary, #2563eb)",
              cursor: "pointer",
              fontSize: "0.875rem",
              fontWeight: 500,
              padding: 0,
            }}
          >
            ← Options List
          </button>
        </div>
      )}

      {/* --- List view --- */}
      {view === "list" && (
        <>
          <div className={styles.sectionHeader}>
            <span className={styles.sectionTitle}>Concept Options</span>
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
              + New Option
            </button>
          </div>

          {error && <ErrorAlert message={error} />}

          {loading && (
            <div
              style={{
                padding: 40,
                textAlign: "center",
                color: "var(--color-text-muted)",
              }}
            >
              Loading concept options…
            </div>
          )}

          {!loading && options.length === 0 && !error && (
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
              <p style={{ margin: 0, fontWeight: 500 }}>No concept options yet</p>
              <p style={{ margin: "8px 0 0", fontSize: "0.875rem" }}>
                Create your first concept option to start designing your
                development programme.
              </p>
            </div>
          )}

          {!loading && options.length > 0 && (
            <OptionsList
              options={options}
              onSelectOption={handleSelectOption}
              onEditOption={handleEditOption}
            />
          )}
        </>
      )}

      {/* --- Detail view --- */}
      {view === "detail" && selectedOption && (
        <DetailView
          option={selectedOption}
          onBack={handleBack}
          onEdit={handleEditOption}
          onRefresh={handleDetailRefresh}
        />
      )}

      {/* --- Compare view --- */}
      {view === "compare" && <ComparisonView />}

      {/* --- Modals --- */}
      {showCreateModal && (
        <ConceptOptionFormModal
          onClose={() => setShowCreateModal(false)}
          onSaved={handleSaved}
        />
      )}

      {editingOption && (
        <ConceptOptionFormModal
          existing={editingOption}
          onClose={() => setEditingOption(null)}
          onSaved={handleSaved}
        />
      )}
    </PageContainer>
  );
}
