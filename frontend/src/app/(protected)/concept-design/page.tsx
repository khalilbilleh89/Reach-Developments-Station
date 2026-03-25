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
 *   DELETE /concept-options/{id}
 *   POST   /concept-options/{id}/duplicate
 *   POST   /concept-options/{id}/unit-mix
 *   GET    /concept-options/{id}/summary
 *   POST   /concept-options/{id}/promote
 *
 * PR-CONCEPT-055, PR-CONCEPT-057, PR-CONCEPT-058, PR-CONCEPT-060
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
  deleteConceptOption,
  duplicateConceptOption,
} from "@/lib/concept-design-api";
import { apiFetch } from "@/lib/api-client";
import { formatCurrency } from "@/lib/format-utils";
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
// Scenario / Land context types — PR-CONCEPT-060
// ---------------------------------------------------------------------------

interface ScenarioOption {
  id: string;
  name: string;
  land_id: string | null;
}

interface LandContext {
  parcel_name: string;
  land_area_sqm: number | null;
  permitted_far: number | null;
  density_ratio: number | null;
  zoning_category: string | null;
}

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
  const [farLimit, setFarLimit] = useState(
    existing?.far_limit != null ? String(existing.far_limit) : "",
  );
  const [densityLimit, setDensityLimit] = useState(
    existing?.density_limit != null ? String(existing.density_limit) : "",
  );

  // Land / Scenario integration — PR-CONCEPT-060
  const [scenarios, setScenarios] = useState<ScenarioOption[]>([]);
  const [landContext, setLandContext] = useState<LandContext | null>(null);
  const [loadingLand, setLoadingLand] = useState(false);
  const [overrideFar, setOverrideFar] = useState(
    existing?.concept_override_far_limit != null
      ? String(existing.concept_override_far_limit)
      : "",
  );
  const [overrideDensity, setOverrideDensity] = useState(
    existing?.concept_override_density_limit != null
      ? String(existing.concept_override_density_limit)
      : "",
  );
  const [showFarOverride, setShowFarOverride] = useState(
    existing?.concept_override_far_limit != null,
  );
  const [showDensityOverride, setShowDensityOverride] = useState(
    existing?.concept_override_density_limit != null,
  );

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load scenarios list for dropdown — PR-CONCEPT-060
  useEffect(() => {
    if (isEdit) return;
    apiFetch<{ items: ScenarioOption[]; total: number }>("/scenarios?limit=100")
      .then((data) => setScenarios(data.items))
      .catch(() => setScenarios([]));
  }, [isEdit]);

  // Fetch land context when a scenario is selected — PR-CONCEPT-060
  useEffect(() => {
    if (!scenarioId) {
      setLandContext(null);
      return;
    }
    const selected = scenarios.find((s) => s.id === scenarioId);
    if (!selected?.land_id) {
      setLandContext(null);
      return;
    }
    setLoadingLand(true);
    apiFetch<LandContext>(`/land/parcels/${encodeURIComponent(selected.land_id)}`)
      .then((parcel) => {
        setLandContext({
          parcel_name: parcel.parcel_name,
          land_area_sqm: parcel.land_area_sqm,
          permitted_far: parcel.permitted_far,
          density_ratio: parcel.density_ratio,
          zoning_category: parcel.zoning_category,
        });
      })
      .catch(() => setLandContext(null))
      .finally(() => setLoadingLand(false));
  }, [scenarioId, scenarios]);

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
            far_limit: farLimit ? parseFloat(farLimit) : null,
            density_limit: densityLimit ? parseFloat(densityLimit) : null,
            concept_override_far_limit:
              showFarOverride && overrideFar ? parseFloat(overrideFar) : null,
            concept_override_density_limit:
              showDensityOverride && overrideDensity
                ? parseFloat(overrideDensity)
                : null,
          });
        } else {
          const payload: ConceptOptionCreate = {
            name: name.trim(),
            description: description.trim() || null,
            status,
            project_id: projectId.trim() || null,
            scenario_id: scenarioId.trim() || null,
            // When a scenario is set, site_area is auto-inherited from the
            // land parcel on the server. Send null unless the user explicitly
            // typed a value, so the server's inheritance logic takes over.
            site_area: siteArea ? parseFloat(siteArea) : null,
            gross_floor_area: grossFloorArea ? parseFloat(grossFloorArea) : null,
            building_count: buildingCount ? parseInt(buildingCount, 10) : null,
            floor_count: floorCount ? parseInt(floorCount, 10) : null,
            // far_limit / density_limit: inherited from land when scenario has a
            // land parcel (hasLandContext). Only send manual values when there is
            // no land context (scenario without land, or no scenario at all).
            far_limit: farLimit && !hasLandContext ? parseFloat(farLimit) : null,
            density_limit:
              densityLimit && !hasLandContext ? parseFloat(densityLimit) : null,
            concept_override_far_limit:
              showFarOverride && overrideFar ? parseFloat(overrideFar) : null,
            concept_override_density_limit:
              showDensityOverride && overrideDensity
                ? parseFloat(overrideDensity)
                : null,
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
      farLimit,
      densityLimit,
      overrideFar,
      overrideDensity,
      showFarOverride,
      showDensityOverride,
      isEdit,
      existing,
      onSaved,
    ],
  );

  const hasLandContext = landContext !== null;

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

            {/* Scenario selector — PR-CONCEPT-060 */}
            <Field label="Scenario" id="co-scenario-id">
              <select
                id="co-scenario-id"
                value={scenarioId}
                onChange={(e) => setScenarioId(e.target.value)}
                style={inputStyle}
              >
                <option value="">— No scenario (manual inputs) —</option>
                {scenarios.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                    {s.land_id ? " 🏗 (with land)" : ""}
                  </option>
                ))}
              </select>
            </Field>

            {/* Land context panel — PR-CONCEPT-060 */}
            {scenarioId && (
              <div
                style={{
                  marginBottom: 16,
                  padding: "12px 16px",
                  background: "#eff6ff",
                  border: "1px solid #bfdbfe",
                  borderRadius: 8,
                  fontSize: "0.875rem",
                }}
              >
                {loadingLand ? (
                  <p style={{ margin: 0, color: "#1d4ed8" }}>
                    Loading land context…
                  </p>
                ) : hasLandContext ? (
                  <>
                    <p
                      style={{
                        margin: "0 0 8px",
                        fontWeight: 600,
                        color: "#1d4ed8",
                      }}
                    >
                      🏗 Land Parcel: {landContext.parcel_name}
                    </p>
                    <dl
                      style={{
                        display: "grid",
                        gridTemplateColumns: "auto 1fr",
                        gap: "4px 12px",
                        margin: 0,
                        color: "#1e40af",
                      }}
                    >
                      <dt style={{ fontWeight: 500 }}>Site Area</dt>
                      <dd style={{ margin: 0 }}>
                        {landContext.land_area_sqm != null
                          ? `${landContext.land_area_sqm.toLocaleString()} m²`
                          : "—"}
                      </dd>
                      <dt style={{ fontWeight: 500 }}>FAR Limit</dt>
                      <dd style={{ margin: 0 }}>
                        {landContext.permitted_far != null
                          ? landContext.permitted_far.toString()
                          : "—"}
                      </dd>
                      <dt style={{ fontWeight: 500 }}>Density Limit</dt>
                      <dd style={{ margin: 0 }}>
                        {landContext.density_ratio != null
                          ? `${landContext.density_ratio} dph`
                          : "—"}
                      </dd>
                      <dt style={{ fontWeight: 500 }}>Zoning</dt>
                      <dd style={{ margin: 0 }}>
                        {landContext.zoning_category ?? "—"}
                      </dd>
                    </dl>
                    <p
                      style={{
                        margin: "8px 0 0",
                        fontSize: "0.8rem",
                        color: "#3b82f6",
                        fontStyle: "italic",
                      }}
                    >
                      These values are inherited automatically. Use overrides
                      below to deviate.
                    </p>
                  </>
                ) : (
                  <p style={{ margin: 0, color: "#6b7280", fontStyle: "italic" }}>
                    This scenario has no linked land parcel — manual inputs will
                    be used.
                  </p>
                )}
              </div>
            )}
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
              style={{
                ...inputStyle,
                background:
                  !isEdit && hasLandContext ? "#f0fdf4" : inputStyle.background,
              }}
              placeholder={
                !isEdit && hasLandContext
                  ? `Inherited: ${landContext?.land_area_sqm ?? "—"} m²`
                  : "e.g. 5000"
              }
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

          {/* FAR / Density shown when no land context is available for the
              selected scenario (or in edit mode). For scenarios with land,
              constraints are inherited — the override section handles deviations. */}
          {(!scenarioId || !hasLandContext || isEdit) && (
            <>
              <Field label="FAR Limit" id="co-far-limit">
                <input
                  id="co-far-limit"
                  type="number"
                  min="0.01"
                  step="any"
                  value={farLimit}
                  onChange={(e) => setFarLimit(e.target.value)}
                  style={inputStyle}
                  placeholder="e.g. 2.5"
                />
              </Field>
              <Field label="Density Limit (dph)" id="co-density-limit">
                <input
                  id="co-density-limit"
                  type="number"
                  min="0.01"
                  step="any"
                  value={densityLimit}
                  onChange={(e) => setDensityLimit(e.target.value)}
                  style={inputStyle}
                  placeholder="dwellings/hectare"
                />
              </Field>
            </>
          )}
        </div>

        {/* Override toggles — PR-CONCEPT-060 */}
        {(hasLandContext || isEdit) && (
          <div
            style={{
              marginTop: 4,
              marginBottom: 16,
              padding: "12px 16px",
              background: "#fefce8",
              border: "1px solid #fde68a",
              borderRadius: 8,
            }}
          >
            <p
              style={{
                margin: "0 0 10px",
                fontSize: "0.8rem",
                fontWeight: 600,
                color: "#92400e",
              }}
            >
              ⚙ Advanced Overrides
            </p>

            <div style={{ marginBottom: 8 }}>
              <label
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  fontSize: "0.875rem",
                  cursor: "pointer",
                  color: "#78350f",
                }}
              >
                <input
                  type="checkbox"
                  checked={showFarOverride}
                  onChange={(e) => {
                    setShowFarOverride(e.target.checked);
                    if (!e.target.checked) setOverrideFar("");
                  }}
                />
                Override FAR Limit
              </label>
              {showFarOverride && (
                <input
                  type="number"
                  min="0.01"
                  step="any"
                  value={overrideFar}
                  onChange={(e) => setOverrideFar(e.target.value)}
                  style={{ ...inputStyle, marginTop: 6 }}
                  placeholder="Override FAR (e.g. 3.0)"
                />
              )}
            </div>

            <div>
              <label
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  fontSize: "0.875rem",
                  cursor: "pointer",
                  color: "#78350f",
                }}
              >
                <input
                  type="checkbox"
                  checked={showDensityOverride}
                  onChange={(e) => {
                    setShowDensityOverride(e.target.checked);
                    if (!e.target.checked) setOverrideDensity("");
                  }}
                />
                Override Density Limit
              </label>
              {showDensityOverride && (
                <input
                  type="number"
                  min="0.01"
                  step="any"
                  value={overrideDensity}
                  onChange={(e) => setOverrideDensity(e.target.value)}
                  style={{ ...inputStyle, marginTop: 6 }}
                  placeholder="Override density (dph)"
                />
              )}
            </div>
          </div>
        )}

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

      // Client-side guard: target_project_id is required when the option has
      // no project_id set. Do not send the request with a null value because
      // the backend will reject it anyway, and the user deserves a clear error.
      if (!conceptOption.project_id && !targetProjectId.trim()) {
        setError("Target Project ID is required to promote this option.");
        return;
      }

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
          <dt style={{ color: "var(--color-text-muted)", fontWeight: 500 }}>Buildings</dt>
          <dd style={{ margin: 0 }}>{result.buildings_created}</dd>
          <dt style={{ color: "var(--color-text-muted)", fontWeight: 500 }}>Floors</dt>
          <dd style={{ margin: 0 }}>{result.floors_created}</dd>
          <dt style={{ color: "var(--color-text-muted)", fontWeight: 500 }}>Units Generated</dt>
          <dd style={{ margin: 0 }}>{result.units_created}</dd>
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

// ---------------------------------------------------------------------------
// Delete confirmation modal — PR-CONCEPT-057
// ---------------------------------------------------------------------------

interface DeleteConceptOptionModalProps {
  option: ConceptOption;
  onClose: () => void;
  onDeleted: () => void;
}

function DeleteConceptOptionModal({
  option,
  onClose,
  onDeleted,
}: DeleteConceptOptionModalProps) {
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleConfirm = useCallback(async () => {
    setDeleting(true);
    setError(null);
    try {
      await deleteConceptOption(option.id);
      onDeleted();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Deletion failed.");
    } finally {
      setDeleting(false);
    }
  }, [option.id, onDeleted]);

  return (
    <ModalWrapper
      title="Delete Concept Option"
      titleId="delete-modal-title"
      onClose={onClose}
    >
      <p
        style={{
          fontSize: "0.875rem",
          color: "var(--color-text)",
          marginTop: 0,
          marginBottom: 20,
        }}
      >
        Are you sure you want to delete{" "}
        <strong>{option.name}</strong>? This action cannot be undone.
      </p>

      {error && <ErrorAlert message={error} />}

      <div style={{ display: "flex", justifyContent: "flex-end", gap: 12, marginTop: 8 }}>
        <button
          type="button"
          onClick={onClose}
          disabled={deleting}
          style={{
            padding: "8px 20px",
            border: "1px solid var(--color-border)",
            borderRadius: 6,
            background: "var(--color-surface)",
            cursor: deleting ? "not-allowed" : "pointer",
            fontSize: "0.875rem",
          }}
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={handleConfirm}
          disabled={deleting}
          style={{
            padding: "8px 20px",
            border: "none",
            borderRadius: 6,
            background: "#dc2626",
            color: "#fff",
            cursor: deleting ? "not-allowed" : "pointer",
            fontSize: "0.875rem",
            fontWeight: 500,
          }}
        >
          {deleting ? "Deleting…" : "Delete"}
        </button>
      </div>
    </ModalWrapper>
  );
}

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
      {/* Land / Scenario context panel — PR-CONCEPT-060 */}
      {summary.land_id && (
        <div
          style={{
            marginBottom: 16,
            padding: "10px 14px",
            background: "#eff6ff",
            border: "1px solid #bfdbfe",
            borderRadius: 8,
            fontSize: "0.8rem",
            color: "#1e40af",
          }}
        >
          <span style={{ fontWeight: 600 }}>🏗 Land Context: </span>
          <span>Land ID {summary.land_id.substring(0, 8)}…</span>
          {summary.site_area != null && (
            <span> · Site: {formatNum(summary.site_area, 0)} m²</span>
          )}
          {summary.concept_override_far_limit != null ? (
            <span> · FAR: {summary.concept_override_far_limit} (override)</span>
          ) : summary.far_limit != null ? (
            <span> · FAR: {summary.far_limit}</span>
          ) : null}
          {summary.concept_override_density_limit != null ? (
            <span>
              {" "}
              · Density: {summary.concept_override_density_limit} dph (override)
            </span>
          ) : summary.density_limit != null ? (
            <span> · Density: {summary.density_limit} dph</span>
          ) : null}
        </div>
      )}

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
          {!option.is_promoted && option.status !== "archived" && (
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
              {option.land_id && (
                <span
                  className={`${styles.badge} ${styles.badgeBlue}`}
                  title={option.land_id}
                  style={{ background: "#eff6ff", color: "#1d4ed8", border: "1px solid #bfdbfe" }}
                >
                  🏗 Land: {option.land_id.substring(0, 8)}…
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
  const [pricePerSqm, setPricePerSqm] = useState("");
  const [priceError, setPriceError] = useState<string | null>(null);
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

      // Validate price input: only pass finite positive numbers; reject 0, negative, NaN, Infinity
      let validatedPrice: number | null = null;
      if (pricePerSqm.trim()) {
        const parsed = parseFloat(pricePerSqm.trim());
        if (!Number.isFinite(parsed) || parsed <= 0) {
          setPriceError("Enter a valid positive price (e.g. 2500).");
          return;
        }
        validatedPrice = parsed;
      }
      setPriceError(null);

      setLoading(true);
      setError(null);

      const params =
        filterType === "project_id"
          ? { project_id: filterId.trim(), price_per_sqm: validatedPrice }
          : { scenario_id: filterId.trim(), price_per_sqm: validatedPrice };

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
    [filterType, filterId, pricePerSqm],
  );

  const hasFinancials = comparison?.rows.some((r) => r.estimated_gdv != null) ?? false;

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
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <input
            type="number"
            min="0.01"
            step="any"
            value={pricePerSqm}
            onChange={(e) => { setPricePerSqm(e.target.value); setPriceError(null); }}
            placeholder="Price / m² (optional)"
            style={{ ...inputStyle, width: 180, borderColor: priceError ? "#dc2626" : undefined }}
            aria-label="Price per sqm"
          />
          {priceError && (
            <span style={{ fontSize: "0.75rem", color: "#dc2626" }}>{priceError}</span>
          )}
        </div>
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
            {hasFinancials && (
              <span> · GDV estimates included</span>
            )}
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
                  {hasFinancials && (
                    <>
                      <th>Est. GDV</th>
                      <th>Revenue / m²</th>
                      <th>Revenue / Unit</th>
                    </>
                  )}
                </tr>
              </thead>
              <tbody>
                {comparison.rows.map((row) => {
                  const isBestPhysical =
                    row.is_best_sellable_area || row.is_best_efficiency || row.is_best_unit_count;
                  const isBestFinancial = row.is_best_gdv;
                  const highlight = isBestPhysical || isBestFinancial;
                  return (
                    <tr
                      key={row.concept_option_id}
                      style={highlight ? { background: "#f0fdf4" } : undefined}
                    >
                      <td>
                        <div style={{ fontWeight: 500 }}>
                          {row.name}
                          {isBestPhysical && (
                            <span
                              className={`${styles.badge} ${styles.badgeGreen}`}
                              style={{ marginLeft: 8 }}
                            >
                              Best
                            </span>
                          )}
                          {isBestFinancial && !isBestPhysical && (
                            <span
                              className={`${styles.badge} ${styles.badgeGreen}`}
                              style={{ marginLeft: 8 }}
                            >
                              Best GDV
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
                      {hasFinancials && (
                        <>
                          <td style={{ fontWeight: row.is_best_gdv ? 600 : undefined }}>
                            {row.estimated_gdv != null ? formatCurrency(row.estimated_gdv) : "—"}
                            {row.is_best_gdv && (
                              <span style={{ marginLeft: 4, color: "#15803d" }}>★</span>
                            )}
                          </td>
                          <td>{row.estimated_revenue_per_sqm != null ? formatCurrency(row.estimated_revenue_per_sqm) : "—"}</td>
                          <td>{row.estimated_revenue_per_unit != null ? formatCurrency(row.estimated_revenue_per_unit) : "—"}</td>
                        </>
                      )}
                    </tr>
                  );
                })}
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
  onDeleteOption: (option: ConceptOption) => void;
  onDuplicateOption: (option: ConceptOption) => void;
  duplicating: boolean;
}

function OptionsList({ options, onSelectOption, onEditOption, onDeleteOption, onDuplicateOption, duplicating }: OptionsListProps) {
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
                <div style={{ display: "flex", gap: 6 }}>
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
                  <button
                    type="button"
                    onClick={() => onDuplicateOption(opt)}
                    disabled={opt.status === "archived" || duplicating}
                    title={opt.status === "archived" ? "Cannot duplicate an archived concept option" : duplicating ? "Duplication in progress…" : "Duplicate option"}
                    style={{
                      padding: "3px 10px",
                      border: "1px solid var(--color-border)",
                      borderRadius: 4,
                      background: (opt.status === "archived" || duplicating) ? "var(--color-surface)" : "#fff",
                      color: (opt.status === "archived" || duplicating) ? "var(--color-text-muted)" : "var(--color-text)",
                      cursor: (opt.status === "archived" || duplicating) ? "not-allowed" : "pointer",
                      fontSize: "0.8rem",
                      opacity: (opt.status === "archived" || duplicating) ? 0.5 : 1,
                    }}
                  >
                    {duplicating ? "Duplicating…" : "Duplicate"}
                  </button>
                  <button
                    type="button"
                    onClick={() => onDeleteOption(opt)}
                    disabled={opt.is_promoted}
                    title={opt.is_promoted ? "Cannot delete a promoted concept option" : "Delete option"}
                    style={{
                      padding: "3px 10px",
                      border: "1px solid #fca5a5",
                      borderRadius: 4,
                      background: opt.is_promoted ? "var(--color-surface)" : "#fff",
                      color: opt.is_promoted ? "var(--color-text-muted)" : "#dc2626",
                      cursor: opt.is_promoted ? "not-allowed" : "pointer",
                      fontSize: "0.8rem",
                      opacity: opt.is_promoted ? 0.5 : 1,
                    }}
                  >
                    Delete
                  </button>
                </div>
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
  const [deletingOption, setDeletingOption] = useState<ConceptOption | null>(null);
  const [duplicating, setDuplicating] = useState(false);
  const [duplicateError, setDuplicateError] = useState<string | null>(null);

  const fetchOptions = useCallback(() => {
    setLoading(true);
    listConceptOptions({ limit: 100 })
      .then((resp) => {
        setOptions(resp.items);
        setTotal(resp.total);
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

  const handleDeleteOption = useCallback((opt: ConceptOption) => {
    setDeletingOption(opt);
  }, []);

  const handleDuplicateOption = useCallback(
    (opt: ConceptOption) => {
      setDuplicateError(null);
      setDuplicating(true);
      duplicateConceptOption(opt.id)
        .then((newOption) => {
          fetchOptions();
          setEditingOption(newOption);
        })
        .catch((err: unknown) => {
          setDuplicateError(
            err instanceof Error ? err.message : "Duplication failed.",
          );
        })
        .finally(() => setDuplicating(false));
    },
    [fetchOptions],
  );

  const handleDeleted = useCallback(() => {
    setDeletingOption(null);
    fetchOptions();
  }, [fetchOptions]);

  const handleSaved = useCallback(() => {
    setShowCreateModal(false);
    setEditingOption(null);
    fetchOptions();
  }, [fetchOptions]);

  const handleDetailRefresh = useCallback(() => {
    fetchOptions();
    // Update selectedOption from the same batch that fetchOptions will load.
    // We issue a second targeted fetch only to get the refreshed record — errors
    // are caught silently because fetchOptions already covers the primary error path.
    if (selectedOption) {
      listConceptOptions({ limit: 100 })
        .then((resp) => {
          const updated = resp.items.find((o) => o.id === selectedOption.id);
          if (updated) setSelectedOption(updated);
        })
        .catch((error: unknown) => {
          console.error("Failed to refresh selected concept option", error);
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
          {duplicateError && <ErrorAlert message={duplicateError} />}

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
              onDeleteOption={handleDeleteOption}
              onDuplicateOption={handleDuplicateOption}
              duplicating={duplicating}
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

      {deletingOption && (
        <DeleteConceptOptionModal
          option={deletingOption}
          onClose={() => setDeletingOption(null)}
          onDeleted={handleDeleted}
        />
      )}
    </PageContainer>
  );
}
