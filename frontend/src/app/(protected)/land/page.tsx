"use client";

import React, { useCallback, useEffect, useState } from "react";
import { PageContainer } from "@/components/shell/PageContainer";
import { MetricCard } from "@/components/dashboard/MetricCard";
import {
  listLandParcels,
  createLandParcel,
  updateLandParcel,
  deleteLandParcel,
} from "@/lib/land-api";
import type { LandParcel, LandParcelCreate, LandStatus } from "@/lib/land-types";
import styles from "@/styles/demo-shell.module.css";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function statusBadgeClass(status: LandStatus): string {
  switch (status) {
    case "approved":
      return styles.badgeGreen;
    case "under_review":
      return styles.badgeBlue;
    case "draft":
      return styles.badgeGray;
    case "archived":
      return styles.badgeGray;
    default:
      return styles.badgeGray;
  }
}

function formatStatus(status: LandStatus): string {
  switch (status) {
    case "draft":
      return "Draft";
    case "under_review":
      return "Under Review";
    case "approved":
      return "Approved";
    case "archived":
      return "Archived";
    default:
      return status;
  }
}

function formatArea(sqm: number | null): string {
  if (sqm === null) return "—";
  return `${sqm.toLocaleString()} m²`;
}

// ---------------------------------------------------------------------------
// Create parcel modal
// ---------------------------------------------------------------------------

interface CreateParcelModalProps {
  onClose: () => void;
  onCreated: () => void;
}

function CreateParcelModal({ onClose, onCreated }: CreateParcelModalProps) {
  const [parcelName, setParcelName] = useState("");
  const [parcelCode, setParcelCode] = useState("");
  const [city, setCity] = useState("");
  const [country, setCountry] = useState("");
  const [landAreaSqm, setLandAreaSqm] = useState("");
  const [zoningCategory, setZoningCategory] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!parcelName.trim() || !parcelCode.trim()) {
        setError("Parcel name and code are required.");
        return;
      }
      setSubmitting(true);
      setError(null);
      const data: LandParcelCreate = {
        parcel_name: parcelName.trim(),
        parcel_code: parcelCode.trim(),
        city: city.trim() || null,
        country: country.trim() || null,
        land_area_sqm: landAreaSqm ? parseFloat(landAreaSqm) : null,
        zoning_category: zoningCategory.trim() || null,
      };
      try {
        await createLandParcel(data);
        onCreated();
      } catch (err: unknown) {
        setError(
          err instanceof Error ? err.message : "Failed to create land parcel.",
        );
      } finally {
        setSubmitting(false);
      }
    },
    [parcelName, parcelCode, city, country, landAreaSqm, zoningCategory, onCreated],
  );

  return (
    <div
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
        <h2 style={{ margin: "0 0 24px", fontSize: "1.125rem", fontWeight: 600 }}>
          New Land Parcel
        </h2>
        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: 16 }}>
            <label style={{ display: "block", marginBottom: 6, fontSize: "0.875rem", fontWeight: 500 }}>
              Parcel Name *
            </label>
            <input
              type="text"
              value={parcelName}
              onChange={(e) => setParcelName(e.target.value)}
              placeholder="e.g. Al Barsha North Site"
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
            <label style={{ display: "block", marginBottom: 6, fontSize: "0.875rem", fontWeight: 500 }}>
              Parcel Code *
            </label>
            <input
              type="text"
              value={parcelCode}
              onChange={(e) => setParcelCode(e.target.value)}
              placeholder="e.g. PCL-001"
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
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}>
            <div>
              <label style={{ display: "block", marginBottom: 6, fontSize: "0.875rem", fontWeight: 500 }}>
                City
              </label>
              <input
                type="text"
                value={city}
                onChange={(e) => setCity(e.target.value)}
                placeholder="e.g. Dubai"
                style={{
                  width: "100%",
                  padding: "8px 12px",
                  border: "1px solid var(--color-border)",
                  borderRadius: 6,
                  fontSize: "0.875rem",
                  boxSizing: "border-box",
                }}
              />
            </div>
            <div>
              <label style={{ display: "block", marginBottom: 6, fontSize: "0.875rem", fontWeight: 500 }}>
                Country
              </label>
              <input
                type="text"
                value={country}
                onChange={(e) => setCountry(e.target.value)}
                placeholder="e.g. UAE"
                style={{
                  width: "100%",
                  padding: "8px 12px",
                  border: "1px solid var(--color-border)",
                  borderRadius: 6,
                  fontSize: "0.875rem",
                  boxSizing: "border-box",
                }}
              />
            </div>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 24 }}>
            <div>
              <label style={{ display: "block", marginBottom: 6, fontSize: "0.875rem", fontWeight: 500 }}>
                Area (m²)
              </label>
              <input
                type="number"
                value={landAreaSqm}
                onChange={(e) => setLandAreaSqm(e.target.value)}
                placeholder="e.g. 10000"
                min={0}
                step={0.01}
                style={{
                  width: "100%",
                  padding: "8px 12px",
                  border: "1px solid var(--color-border)",
                  borderRadius: 6,
                  fontSize: "0.875rem",
                  boxSizing: "border-box",
                }}
              />
            </div>
            <div>
              <label style={{ display: "block", marginBottom: 6, fontSize: "0.875rem", fontWeight: 500 }}>
                Zoning
              </label>
              <input
                type="text"
                value={zoningCategory}
                onChange={(e) => setZoningCategory(e.target.value)}
                placeholder="e.g. Residential"
                style={{
                  width: "100%",
                  padding: "8px 12px",
                  border: "1px solid var(--color-border)",
                  borderRadius: 6,
                  fontSize: "0.875rem",
                  boxSizing: "border-box",
                }}
              />
            </div>
          </div>
          {error && (
            <p style={{ color: "#b91c1c", fontSize: "0.875rem", marginBottom: 16 }}>
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
              {submitting ? "Creating…" : "Create Parcel"}
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
 * Land inventory page — land parcel management dashboard.
 *
 * Shows KPI summary and a table of land parcels. Supports create,
 * status update, and delete operations.
 */
export default function LandPage() {
  const [parcels, setParcels] = useState<LandParcel[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const fetchParcels = useCallback(() => {
    setLoading(true);
    listLandParcels({ limit: 100 })
      .then((resp) => {
        setParcels(resp.items);
        setTotal(resp.total);
        setError(null);
      })
      .catch((err: unknown) => {
        setError(
          err instanceof Error ? err.message : "Failed to load land parcels.",
        );
        setParcels([]);
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    fetchParcels();
  }, [fetchParcels]);

  const handleCreated = useCallback(() => {
    setShowCreateModal(false);
    fetchParcels();
  }, [fetchParcels]);

  const handleStatusChange = useCallback(
    async (parcelId: string, newStatus: LandStatus) => {
      try {
        await updateLandParcel(parcelId, { status: newStatus });
        fetchParcels();
      } catch (err: unknown) {
        setError(
          err instanceof Error ? err.message : "Failed to update parcel status.",
        );
      }
    },
    [fetchParcels],
  );

  const handleDelete = useCallback(
    async (parcelId: string) => {
      if (!confirm("Delete this land parcel? This action cannot be undone.")) {
        return;
      }
      setDeletingId(parcelId);
      try {
        await deleteLandParcel(parcelId);
        fetchParcels();
      } catch (err: unknown) {
        setError(
          err instanceof Error ? err.message : "Failed to delete land parcel.",
        );
      } finally {
        setDeletingId(null);
      }
    },
    [fetchParcels],
  );

  // KPI counts
  const draftCount = parcels.filter((p) => p.status === "draft").length;
  const underReviewCount = parcels.filter((p) => p.status === "under_review").length;
  const approvedCount = parcels.filter((p) => p.status === "approved").length;
  const totalAreaSqm = parcels.reduce((sum, p) => sum + (p.land_area_sqm ?? 0), 0);

  return (
    <PageContainer
      title="Land Inventory"
      subtitle="Manage land parcels, track acquisition status, and link to projects."
    >
      {/* KPI row */}
      <div className={styles.kpiGrid}>
        <MetricCard title="Total Parcels" value={String(total)} />
        <MetricCard title="Draft" value={String(draftCount)} />
        <MetricCard title="Under Review" value={String(underReviewCount)} />
        <MetricCard title="Approved" value={String(approvedCount)} />
      </div>

      {/* Total area summary */}
      {totalAreaSqm > 0 && (
        <div className={styles.kpiGrid3} style={{ marginBottom: "var(--space-6)" }}>
          <MetricCard
            title="Total Land Area"
            value={`${totalAreaSqm.toLocaleString()} m²`}
          />
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
          Land Parcels
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
          + New Parcel
        </button>
      </div>

      {/* Error state */}
      {error && (
        <div
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
        <div style={{ padding: 40, textAlign: "center", color: "var(--color-text-muted)" }}>
          Loading land parcels…
        </div>
      )}

      {/* Empty state */}
      {!loading && parcels.length === 0 && !error && (
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
          <div style={{ fontSize: "2rem", marginBottom: 12 }}>🏗</div>
          <p style={{ margin: 0, fontWeight: 500 }}>No land parcels yet</p>
          <p style={{ margin: "8px 0 0", fontSize: "0.875rem" }}>
            Create your first land parcel to start tracking your land bank.
          </p>
        </div>
      )}

      {/* Parcels table */}
      {!loading && parcels.length > 0 && (
        <div className={styles.tableWrapper}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Name</th>
                <th>Code</th>
                <th>Location</th>
                <th>Area</th>
                <th>Zoning</th>
                <th>Status</th>
                <th>Project</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {parcels.map((parcel) => (
                <tr key={parcel.id}>
                  <td style={{ fontWeight: 500 }}>{parcel.parcel_name}</td>
                  <td style={{ fontFamily: "monospace", fontSize: "0.8rem" }}>
                    {parcel.parcel_code}
                  </td>
                  <td>
                    {[parcel.city, parcel.country].filter(Boolean).join(", ") || "—"}
                  </td>
                  <td>{formatArea(parcel.land_area_sqm)}</td>
                  <td>{parcel.zoning_category ?? "—"}</td>
                  <td>
                    <span className={`${styles.badge} ${statusBadgeClass(parcel.status)}`}>
                      {formatStatus(parcel.status)}
                    </span>
                  </td>
                  <td style={{ fontSize: "0.8rem", color: "var(--color-text-muted)" }}>
                    {parcel.project_id ? (
                      <span style={{ fontFamily: "monospace" }}>
                        {parcel.project_id.substring(0, 8)}…
                      </span>
                    ) : (
                      <em>Unassigned</em>
                    )}
                  </td>
                  <td>
                    <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                      <select
                        value={parcel.status}
                        onChange={(e) =>
                          handleStatusChange(parcel.id, e.target.value as LandStatus)
                        }
                        style={{
                          padding: "4px 8px",
                          border: "1px solid var(--color-border)",
                          borderRadius: 4,
                          fontSize: "0.8rem",
                          background: "var(--color-surface)",
                          cursor: "pointer",
                        }}
                        aria-label={`Change status for ${parcel.parcel_name}`}
                      >
                        <option value="draft">Draft</option>
                        <option value="under_review">Under Review</option>
                        <option value="approved">Approved</option>
                        <option value="archived">Archived</option>
                      </select>
                      <button
                        type="button"
                        onClick={() => handleDelete(parcel.id)}
                        disabled={deletingId === parcel.id}
                        style={{
                          padding: "4px 10px",
                          border: "1px solid #fca5a5",
                          borderRadius: 4,
                          background: "#fef2f2",
                          color: "#b91c1c",
                          cursor: deletingId === parcel.id ? "not-allowed" : "pointer",
                          fontSize: "0.8rem",
                        }}
                        aria-label={`Delete ${parcel.parcel_name}`}
                      >
                        {deletingId === parcel.id ? "…" : "Delete"}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create modal */}
      {showCreateModal && (
        <CreateParcelModal
          onClose={() => setShowCreateModal(false)}
          onCreated={handleCreated}
        />
      )}
    </PageContainer>
  );
}
