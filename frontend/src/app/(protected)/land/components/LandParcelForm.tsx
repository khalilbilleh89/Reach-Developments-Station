"use client";

/**
 * LandParcelForm
 *
 * Structured edit form for land parcel underwriting inputs.
 * Fields are grouped into four sections:
 *   1. Identity & Cadastral
 *   2. Physical / Zoning
 *   3. Acquisition Economics
 *   4. Notes / Provenance
 *
 * Computed metrics are never included here — they are displayed separately
 * in LandParcelMetricsPanel.
 */

import React, { useCallback, useState } from "react";
import type { LandParcel, LandParcelCreate, LandParcelUpdate, LandStatus } from "@/lib/land-types";
import { DEFAULT_CURRENCY } from "@/lib/currency-constants";

// ---------------------------------------------------------------------------
// Section card helper
// ---------------------------------------------------------------------------

interface SectionCardProps {
  title: string;
  children: React.ReactNode;
}

function SectionCard({ title, children }: SectionCardProps) {
  return (
    <div
      style={{
        marginBottom: 20,
        border: "1px solid var(--color-border)",
        borderRadius: 8,
        overflow: "hidden",
      }}
    >
      <div
        style={{
          padding: "8px 16px",
          background: "var(--color-surface-alt, #f9fafb)",
          borderBottom: "1px solid var(--color-border)",
          fontSize: "0.75rem",
          fontWeight: 600,
          textTransform: "uppercase" as const,
          letterSpacing: "0.05em",
          color: "var(--color-text-muted)",
        }}
      >
        {title}
      </div>
      <div style={{ padding: "16px" }}>{children}</div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Field helpers
// ---------------------------------------------------------------------------

const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: "7px 10px",
  border: "1px solid var(--color-border)",
  borderRadius: 6,
  fontSize: "0.875rem",
  boxSizing: "border-box",
  background: "var(--color-surface)",
  color: "var(--color-text)",
};

const labelStyle: React.CSSProperties = {
  display: "block",
  marginBottom: 4,
  fontSize: "0.8rem",
  fontWeight: 500,
  color: "var(--color-text-muted)",
};

interface FieldProps {
  label: string;
  htmlFor: string;
  children: React.ReactNode;
}

function Field({ label, htmlFor, children }: FieldProps) {
  return (
    <div style={{ marginBottom: 12 }}>
      <label htmlFor={htmlFor} style={labelStyle}>{label}</label>
      {children}
    </div>
  );
}

function Row({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(2, 1fr)",
        gap: 12,
      }}
    >
      {children}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Form state shape
// ---------------------------------------------------------------------------

interface FormState {
  parcel_name: string;
  parcel_code: string;
  // Location
  country: string;
  city: string;
  district: string;
  address: string;
  municipality: string;
  submarket: string;
  // Cadastral
  plot_number: string;
  cadastral_id: string;
  title_reference: string;
  location_link: string;
  // Physical
  land_area_sqm: string;
  frontage_m: string;
  depth_m: string;
  buildable_area_sqm: string;
  sellable_area_sqm: string;
  coverage_ratio: string;
  density_ratio: string;
  front_setback_m: string;
  side_setback_m: string;
  rear_setback_m: string;
  zoning_category: string;
  permitted_far: string;
  max_height_m: string;
  max_floors: string;
  corner_plot: boolean;
  utilities_available: boolean;
  access_notes: string;
  utilities_notes: string;
  // Economics
  acquisition_price: string;
  transaction_cost: string;
  currency: string;
  asking_price_per_sqm: string;
  supported_price_per_sqm: string;
  // Notes
  assumption_notes: string;
  source_notes: string;
  status: LandStatus;
}

function parcelToFormState(parcel: LandParcel | null): FormState {
  const s = (v: string | null | undefined) => v ?? "";
  const n = (v: number | null | undefined) => (v !== null && v !== undefined ? String(v) : "");
  return {
    parcel_name: s(parcel?.parcel_name),
    parcel_code: s(parcel?.parcel_code),
    country: s(parcel?.country),
    city: s(parcel?.city),
    district: s(parcel?.district),
    address: s(parcel?.address),
    municipality: s(parcel?.municipality),
    submarket: s(parcel?.submarket),
    plot_number: s(parcel?.plot_number),
    cadastral_id: s(parcel?.cadastral_id),
    title_reference: s(parcel?.title_reference),
    location_link: s(parcel?.location_link),
    land_area_sqm: n(parcel?.land_area_sqm),
    frontage_m: n(parcel?.frontage_m),
    depth_m: n(parcel?.depth_m),
    buildable_area_sqm: n(parcel?.buildable_area_sqm),
    sellable_area_sqm: n(parcel?.sellable_area_sqm),
    coverage_ratio: parcel?.coverage_ratio != null ? String(parcel.coverage_ratio * 100) : "",
    density_ratio: n(parcel?.density_ratio),
    front_setback_m: n(parcel?.front_setback_m),
    side_setback_m: n(parcel?.side_setback_m),
    rear_setback_m: n(parcel?.rear_setback_m),
    zoning_category: s(parcel?.zoning_category),
    permitted_far: n(parcel?.permitted_far),
    max_height_m: n(parcel?.max_height_m),
    max_floors: n(parcel?.max_floors),
    corner_plot: parcel?.corner_plot ?? false,
    utilities_available: parcel?.utilities_available ?? false,
    access_notes: s(parcel?.access_notes),
    utilities_notes: s(parcel?.utilities_notes),
    acquisition_price: n(parcel?.acquisition_price),
    transaction_cost: n(parcel?.transaction_cost),
    currency: parcel ? s(parcel.currency) : DEFAULT_CURRENCY,
    asking_price_per_sqm: n(parcel?.asking_price_per_sqm),
    supported_price_per_sqm: n(parcel?.supported_price_per_sqm),
    assumption_notes: s(parcel?.assumption_notes),
    source_notes: s(parcel?.source_notes),
    status: parcel?.status ?? "draft",
  };
}

function formStateToCreate(f: FormState): LandParcelCreate {
  const optStr = (v: string) => (v.trim() ? v.trim() : null);
  const optNum = (v: string) => (v.trim() ? parseFloat(v) : null);
  const optInt = (v: string) => (v.trim() ? parseInt(v, 10) : null);
  return {
    parcel_name: f.parcel_name.trim(),
    parcel_code: f.parcel_code.trim(),
    country: optStr(f.country),
    city: optStr(f.city),
    district: optStr(f.district),
    address: optStr(f.address),
    municipality: optStr(f.municipality),
    submarket: optStr(f.submarket),
    plot_number: optStr(f.plot_number),
    cadastral_id: optStr(f.cadastral_id),
    title_reference: optStr(f.title_reference),
    location_link: optStr(f.location_link),
    land_area_sqm: optNum(f.land_area_sqm),
    frontage_m: optNum(f.frontage_m),
    depth_m: optNum(f.depth_m),
    buildable_area_sqm: optNum(f.buildable_area_sqm),
    sellable_area_sqm: optNum(f.sellable_area_sqm),
    coverage_ratio: f.coverage_ratio.trim() ? parseFloat(f.coverage_ratio) / 100 : null,
    density_ratio: optNum(f.density_ratio),
    front_setback_m: optNum(f.front_setback_m),
    side_setback_m: optNum(f.side_setback_m),
    rear_setback_m: optNum(f.rear_setback_m),
    zoning_category: optStr(f.zoning_category),
    permitted_far: optNum(f.permitted_far),
    max_height_m: optNum(f.max_height_m),
    max_floors: optInt(f.max_floors),
    corner_plot: f.corner_plot,
    utilities_available: f.utilities_available,
    access_notes: optStr(f.access_notes),
    utilities_notes: optStr(f.utilities_notes),
    acquisition_price: optNum(f.acquisition_price),
    transaction_cost: optNum(f.transaction_cost),
    currency: optStr(f.currency),
    asking_price_per_sqm: optNum(f.asking_price_per_sqm),
    supported_price_per_sqm: optNum(f.supported_price_per_sqm),
    assumption_notes: optStr(f.assumption_notes),
    source_notes: optStr(f.source_notes),
    status: f.status,
  };
}

function formStateToUpdate(f: FormState): LandParcelUpdate {
  const optStr = (v: string) => (v.trim() ? v.trim() : null);
  const optNum = (v: string) => (v.trim() ? parseFloat(v) : null);
  const optInt = (v: string) => (v.trim() ? parseInt(v, 10) : null);
  return {
    parcel_name: f.parcel_name.trim() || null,
    country: optStr(f.country),
    city: optStr(f.city),
    district: optStr(f.district),
    address: optStr(f.address),
    municipality: optStr(f.municipality),
    submarket: optStr(f.submarket),
    plot_number: optStr(f.plot_number),
    cadastral_id: optStr(f.cadastral_id),
    title_reference: optStr(f.title_reference),
    location_link: optStr(f.location_link),
    land_area_sqm: optNum(f.land_area_sqm),
    frontage_m: optNum(f.frontage_m),
    depth_m: optNum(f.depth_m),
    buildable_area_sqm: optNum(f.buildable_area_sqm),
    sellable_area_sqm: optNum(f.sellable_area_sqm),
    coverage_ratio: f.coverage_ratio.trim() ? parseFloat(f.coverage_ratio) / 100 : null,
    density_ratio: optNum(f.density_ratio),
    front_setback_m: optNum(f.front_setback_m),
    side_setback_m: optNum(f.side_setback_m),
    rear_setback_m: optNum(f.rear_setback_m),
    zoning_category: optStr(f.zoning_category),
    permitted_far: optNum(f.permitted_far),
    max_height_m: optNum(f.max_height_m),
    max_floors: optInt(f.max_floors),
    corner_plot: f.corner_plot,
    utilities_available: f.utilities_available,
    access_notes: optStr(f.access_notes),
    utilities_notes: optStr(f.utilities_notes),
    acquisition_price: optNum(f.acquisition_price),
    transaction_cost: optNum(f.transaction_cost),
    currency: optStr(f.currency),
    asking_price_per_sqm: optNum(f.asking_price_per_sqm),
    supported_price_per_sqm: optNum(f.supported_price_per_sqm),
    assumption_notes: optStr(f.assumption_notes),
    source_notes: optStr(f.source_notes),
    status: f.status,
  };
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface LandParcelFormProps {
  /** null = create mode, LandParcel = edit mode */
  parcel: LandParcel | null;
  onSave: (data: LandParcelCreate | LandParcelUpdate) => Promise<void>;
  onCancel: () => void;
}

// ---------------------------------------------------------------------------
// Form component
// ---------------------------------------------------------------------------

export function LandParcelForm({ parcel, onSave, onCancel }: LandParcelFormProps) {
  const isEdit = parcel !== null;
  const [form, setForm] = useState<FormState>(() => parcelToFormState(parcel));
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const set = useCallback(
    (field: keyof FormState, value: string | boolean) =>
      setForm((prev) => ({ ...prev, [field]: value })),
    [],
  );

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!form.parcel_name.trim()) {
        setError("Parcel name is required.");
        return;
      }
      if (!isEdit && !form.parcel_code.trim()) {
        setError("Parcel code is required.");
        return;
      }
      setSubmitting(true);
      setError(null);
      try {
        const data = isEdit ? formStateToUpdate(form) : formStateToCreate(form);
        await onSave(data);
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Failed to save parcel.");
      } finally {
        setSubmitting(false);
      }
    },
    [form, isEdit, onSave],
  );

  return (
    <form onSubmit={handleSubmit}>
      {/* ── Section 1: Identity & Cadastral ──────────────────────────── */}
      <SectionCard title="Identity & Cadastral">
        <Row>
          <Field label="Parcel Name *" htmlFor="parcel_name">
            <input
              id="parcel_name"
              type="text"
              style={inputStyle}
              value={form.parcel_name}
              onChange={(e) => set("parcel_name", e.target.value)}
              placeholder="e.g. Al Barsha North Site"
              required
            />
          </Field>
          {!isEdit ? (
            <Field label="Parcel Code *" htmlFor="parcel_code">
              <input
                id="parcel_code"
                type="text"
                style={inputStyle}
                value={form.parcel_code}
                onChange={(e) => set("parcel_code", e.target.value)}
                placeholder="e.g. PCL-001"
                required
              />
            </Field>
          ) : (
            <Field label="Parcel Code" htmlFor="parcel_code_readonly">
              <input
                id="parcel_code_readonly"
                type="text"
                style={{ ...inputStyle, background: "var(--color-surface-alt, #f9fafb)", cursor: "not-allowed" }}
                value={form.parcel_code}
                readOnly
                title="Parcel code cannot be changed after creation"
              />
            </Field>
          )}
        </Row>
        <Row>
          <Field label="City" htmlFor="city">
            <input
              id="city"
              type="text"
              style={inputStyle}
              value={form.city}
              onChange={(e) => set("city", e.target.value)}
              placeholder="e.g. Dubai"
            />
          </Field>
          <Field label="Country" htmlFor="country">
            <input
              id="country"
              type="text"
              style={inputStyle}
              value={form.country}
              onChange={(e) => set("country", e.target.value)}
              placeholder="e.g. UAE"
            />
          </Field>
        </Row>
        <Row>
          <Field label="District" htmlFor="district">
            <input
              id="district"
              type="text"
              style={inputStyle}
              value={form.district}
              onChange={(e) => set("district", e.target.value)}
              placeholder="e.g. Al Barsha"
            />
          </Field>
          <Field label="Municipality" htmlFor="municipality">
            <input
              id="municipality"
              type="text"
              style={inputStyle}
              value={form.municipality}
              onChange={(e) => set("municipality", e.target.value)}
              placeholder="e.g. Dubai Municipality"
            />
          </Field>
        </Row>
        <Row>
          <Field label="Submarket" htmlFor="submarket">
            <input
              id="submarket"
              type="text"
              style={inputStyle}
              value={form.submarket}
              onChange={(e) => set("submarket", e.target.value)}
              placeholder="e.g. JVC"
            />
          </Field>
          <Field label="Plot Number" htmlFor="plot_number">
            <input
              id="plot_number"
              type="text"
              style={inputStyle}
              value={form.plot_number}
              onChange={(e) => set("plot_number", e.target.value)}
              placeholder="e.g. 1234-A"
            />
          </Field>
        </Row>
        <Row>
          <Field label="Cadastral ID" htmlFor="cadastral_id">
            <input
              id="cadastral_id"
              type="text"
              style={inputStyle}
              value={form.cadastral_id}
              onChange={(e) => set("cadastral_id", e.target.value)}
              placeholder="e.g. 12345"
            />
          </Field>
          <Field label="Title Reference" htmlFor="title_reference">
            <input
              id="title_reference"
              type="text"
              style={inputStyle}
              value={form.title_reference}
              onChange={(e) => set("title_reference", e.target.value)}
              placeholder="e.g. Title Deed No."
            />
          </Field>
        </Row>
        <Field label="Address" htmlFor="address">
          <input
            id="address"
            type="text"
            style={inputStyle}
            value={form.address}
            onChange={(e) => set("address", e.target.value)}
            placeholder="Full address"
          />
        </Field>
        <Field label="Location Link (URL)" htmlFor="location_link">
          <input
            id="location_link"
            type="url"
            style={inputStyle}
            value={form.location_link}
            onChange={(e) => set("location_link", e.target.value)}
            placeholder="https://maps.google.com/…"
          />
        </Field>
      </SectionCard>

      {/* ── Section 2: Physical / Zoning ─────────────────────────────── */}
      <SectionCard title="Physical / Zoning">
        <Row>
          <Field label="Land Area (m²)" htmlFor="land_area_sqm">
            <input
              id="land_area_sqm"
              type="number"
              style={inputStyle}
              value={form.land_area_sqm}
              onChange={(e) => set("land_area_sqm", e.target.value)}
              placeholder="e.g. 10000"
              min={0.01}
              step={0.01}
            />
          </Field>
          <Field label="Permitted FAR" htmlFor="permitted_far">
            <input
              id="permitted_far"
              type="number"
              style={inputStyle}
              value={form.permitted_far}
              onChange={(e) => set("permitted_far", e.target.value)}
              placeholder="e.g. 2.5"
              min={0.01}
              step={0.01}
            />
          </Field>
        </Row>
        <Row>
          <Field label="Buildable Area (m²)" htmlFor="buildable_area_sqm">
            <input
              id="buildable_area_sqm"
              type="number"
              style={inputStyle}
              value={form.buildable_area_sqm}
              onChange={(e) => set("buildable_area_sqm", e.target.value)}
              placeholder="e.g. 25000"
              min={0.01}
              step={0.01}
            />
          </Field>
          <Field label="Sellable Area (m²)" htmlFor="sellable_area_sqm">
            <input
              id="sellable_area_sqm"
              type="number"
              style={inputStyle}
              value={form.sellable_area_sqm}
              onChange={(e) => set("sellable_area_sqm", e.target.value)}
              placeholder="e.g. 20000"
              min={0.01}
              step={0.01}
            />
          </Field>
        </Row>
        <Row>
          <Field label="Frontage (m)" htmlFor="frontage_m">
            <input
              id="frontage_m"
              type="number"
              style={inputStyle}
              value={form.frontage_m}
              onChange={(e) => set("frontage_m", e.target.value)}
              placeholder="e.g. 50"
              min={0.01}
              step={0.01}
            />
          </Field>
          <Field label="Depth (m)" htmlFor="depth_m">
            <input
              id="depth_m"
              type="number"
              style={inputStyle}
              value={form.depth_m}
              onChange={(e) => set("depth_m", e.target.value)}
              placeholder="e.g. 200"
              min={0.01}
              step={0.01}
            />
          </Field>
        </Row>
        <Row>
          <Field label="Zoning Category" htmlFor="zoning_category">
            <input
              id="zoning_category"
              type="text"
              style={inputStyle}
              value={form.zoning_category}
              onChange={(e) => set("zoning_category", e.target.value)}
              placeholder="e.g. Residential"
            />
          </Field>
          <Field label="Max Height (m)" htmlFor="max_height_m">
            <input
              id="max_height_m"
              type="number"
              style={inputStyle}
              value={form.max_height_m}
              onChange={(e) => set("max_height_m", e.target.value)}
              placeholder="e.g. 45"
              min={0.01}
              step={0.01}
            />
          </Field>
        </Row>
        <Row>
          <Field label="Max Floors" htmlFor="max_floors">
            <input
              id="max_floors"
              type="number"
              style={inputStyle}
              value={form.max_floors}
              onChange={(e) => set("max_floors", e.target.value)}
              placeholder="e.g. 12"
              min={1}
              step={1}
            />
          </Field>
          <Field label="Coverage Ratio (%)" htmlFor="coverage_ratio">
            <input
              id="coverage_ratio"
              type="number"
              style={inputStyle}
              value={form.coverage_ratio}
              onChange={(e) => set("coverage_ratio", e.target.value)}
              placeholder="e.g. 50 for 50%"
              min={0}
              max={100}
              step={0.1}
            />
          </Field>
        </Row>
        <Row>
          <Field label="Density Ratio" htmlFor="density_ratio">
            <input
              id="density_ratio"
              type="number"
              style={inputStyle}
              value={form.density_ratio}
              onChange={(e) => set("density_ratio", e.target.value)}
              placeholder="e.g. 1.5"
              min={0}
              step={0.01}
            />
          </Field>
          <div />
        </Row>
        <Row>
          <Field label="Front Setback (m)" htmlFor="front_setback_m">
            <input
              id="front_setback_m"
              type="number"
              style={inputStyle}
              value={form.front_setback_m}
              onChange={(e) => set("front_setback_m", e.target.value)}
              placeholder="e.g. 5"
              min={0}
              step={0.1}
            />
          </Field>
          <Field label="Side Setback (m)" htmlFor="side_setback_m">
            <input
              id="side_setback_m"
              type="number"
              style={inputStyle}
              value={form.side_setback_m}
              onChange={(e) => set("side_setback_m", e.target.value)}
              placeholder="e.g. 3"
              min={0}
              step={0.1}
            />
          </Field>
        </Row>
        <Field label="Rear Setback (m)" htmlFor="rear_setback_m">
          <input
            id="rear_setback_m"
            type="number"
            style={{ ...inputStyle, maxWidth: "calc(50% - 6px)" }}
            value={form.rear_setback_m}
            onChange={(e) => set("rear_setback_m", e.target.value)}
            placeholder="e.g. 3"
            min={0}
            step={0.1}
          />
        </Field>
        <div style={{ display: "flex", gap: 24, marginTop: 8 }}>
          <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "0.875rem", cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={form.corner_plot}
              onChange={(e) => set("corner_plot", e.target.checked)}
            />
            Corner Plot
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "0.875rem", cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={form.utilities_available}
              onChange={(e) => set("utilities_available", e.target.checked)}
            />
            Utilities Available
          </label>
        </div>
        {form.utilities_available && (
          <Field label="Utilities Notes" htmlFor="utilities_notes">
            <textarea
              id="utilities_notes"
              style={{ ...inputStyle, resize: "vertical", minHeight: 60 }}
              value={form.utilities_notes}
              onChange={(e) => set("utilities_notes", e.target.value)}
              placeholder="Describe available utilities"
            />
          </Field>
        )}
        <Field label="Access Notes" htmlFor="access_notes">
          <textarea
            id="access_notes"
            style={{ ...inputStyle, resize: "vertical", minHeight: 60 }}
            value={form.access_notes}
            onChange={(e) => set("access_notes", e.target.value)}
            placeholder="Road access, easements, restrictions…"
          />
        </Field>
      </SectionCard>

      {/* ── Section 3: Acquisition Economics ────────────────────────── */}
      <SectionCard title="Acquisition Economics">
        <Row>
          <Field label="Acquisition Price" htmlFor="acquisition_price">
            <input
              id="acquisition_price"
              type="number"
              style={inputStyle}
              value={form.acquisition_price}
              onChange={(e) => set("acquisition_price", e.target.value)}
              placeholder="e.g. 5500000"
              min={0}
              step="any"
            />
          </Field>
          <Field label="Transaction Cost" htmlFor="transaction_cost">
            <input
              id="transaction_cost"
              type="number"
              style={inputStyle}
              value={form.transaction_cost}
              onChange={(e) => set("transaction_cost", e.target.value)}
              placeholder="e.g. 220000"
              min={0}
              step="any"
            />
          </Field>
        </Row>
        <Row>
          <Field label="Currency" htmlFor="currency">
            <input
              id="currency"
              type="text"
              style={inputStyle}
              value={form.currency}
              onChange={(e) => set("currency", e.target.value)}
              placeholder="e.g. AED, USD, JOD"
              maxLength={10}
            />
          </Field>
          <Field label="Asking Price / m²" htmlFor="asking_price_per_sqm">
            <input
              id="asking_price_per_sqm"
              type="number"
              style={inputStyle}
              value={form.asking_price_per_sqm}
              onChange={(e) => set("asking_price_per_sqm", e.target.value)}
              placeholder="e.g. 5500"
              min={0}
              step="any"
            />
          </Field>
        </Row>
        <Row>
          <Field label="Supported Price / m²" htmlFor="supported_price_per_sqm">
            <input
              id="supported_price_per_sqm"
              type="number"
              style={inputStyle}
              value={form.supported_price_per_sqm}
              onChange={(e) => set("supported_price_per_sqm", e.target.value)}
              placeholder="e.g. 4800"
              min={0}
              step="any"
            />
          </Field>
          <div />
        </Row>
        <Field label="Status" htmlFor="status">
          <select
            id="status"
            style={inputStyle}
            value={form.status}
            onChange={(e) => set("status", e.target.value as LandStatus)}
          >
            <option value="draft">Draft</option>
            <option value="under_review">Under Review</option>
            <option value="approved">Approved</option>
            <option value="archived">Archived</option>
          </select>
        </Field>
      </SectionCard>

      {/* ── Section 4: Notes / Provenance ───────────────────────────── */}
      <SectionCard title="Notes / Provenance">
        <Field label="Assumption Notes" htmlFor="assumption_notes">
          <textarea
            id="assumption_notes"
            style={{ ...inputStyle, resize: "vertical", minHeight: 72 }}
            value={form.assumption_notes}
            onChange={(e) => set("assumption_notes", e.target.value)}
            placeholder="Key assumptions, deal context, buyer/seller notes…"
          />
        </Field>
        <Field label="Source Notes" htmlFor="source_notes">
          <textarea
            id="source_notes"
            style={{ ...inputStyle, resize: "vertical", minHeight: 72 }}
            value={form.source_notes}
            onChange={(e) => set("source_notes", e.target.value)}
            placeholder="Data source, broker name, date of quote…"
          />
        </Field>
      </SectionCard>

      {/* ── Error message ────────────────────────────────────────────── */}
      {error && (
        <p style={{ color: "#b91c1c", fontSize: "0.875rem", marginBottom: 16 }}>
          {error}
        </p>
      )}

      {/* ── Actions ──────────────────────────────────────────────────── */}
      <div style={{ display: "flex", gap: 12, justifyContent: "flex-end" }}>
        <button
          type="button"
          onClick={onCancel}
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
          {submitting ? "Saving…" : isEdit ? "Save Changes" : "Create Parcel"}
        </button>
      </div>
    </form>
  );
}
