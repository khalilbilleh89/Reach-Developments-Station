"use client";

import React, { useCallback, useEffect, useState } from "react";
import { PageContainer } from "@/components/shell/PageContainer";
import { MetricCard } from "@/components/dashboard/MetricCard";
import {
  listLandParcels,
  createLandParcel,
  updateLandParcel,
  deleteLandParcel,
  getLandParcel,
} from "@/lib/land-api";
import type {
  LandParcel,
  LandParcelCreate,
  LandParcelUpdate,
  LandStatus,
} from "@/lib/land-types";
import { LandParcelForm } from "./components/LandParcelForm";
import { LandParcelMetricsPanel } from "./components/LandParcelMetricsPanel";
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

function formatCurrency(value: number | null, currency?: string | null): string {
  if (value === null || value === undefined) return "—";
  const prefix = currency ? `${currency} ` : "";
  if (Math.abs(value) >= 1_000_000) {
    return `${prefix}${(value / 1_000_000).toFixed(2)}M`;
  }
  if (Math.abs(value) >= 1_000) {
    return `${prefix}${(value / 1_000).toFixed(1)}K`;
  }
  return `${prefix}${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function formatPerSqm(value: number | null): string {
  if (value === null || value === undefined) return "—";
  return value.toLocaleString(undefined, { maximumFractionDigits: 0 }) + " /m²";
}

// ---------------------------------------------------------------------------
// Shared modal shell
// ---------------------------------------------------------------------------

interface ModalShellProps {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  wide?: boolean;
}

function ModalShell({ title, onClose, children, wide }: ModalShellProps) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="parcel-dialog-title"
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
          width: wide ? 760 : 520,
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
            id="parcel-dialog-title"
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
// Create parcel modal
// ---------------------------------------------------------------------------

interface CreateParcelModalProps {
  onClose: () => void;
  onCreated: () => void;
}

function CreateParcelModal({ onClose, onCreated }: CreateParcelModalProps) {
  const handleSave = useCallback(
    async (data: LandParcelCreate | LandParcelUpdate) => {
      await createLandParcel(data as LandParcelCreate);
      onCreated();
    },
    [onCreated],
  );

  return (
    <ModalShell title="New Land Parcel" onClose={onClose} wide>
      <LandParcelForm parcel={null} onSave={handleSave} onCancel={onClose} />
    </ModalShell>
  );
}

// ---------------------------------------------------------------------------
// Edit parcel modal
// ---------------------------------------------------------------------------

interface EditParcelModalProps {
  parcel: LandParcel;
  onClose: () => void;
  onSaved: () => void;
}

function EditParcelModal({ parcel, onClose, onSaved }: EditParcelModalProps) {
  const [updatedParcel, setUpdatedParcel] = useState<LandParcel>(parcel);

  const handleSave = useCallback(
    async (data: LandParcelCreate | LandParcelUpdate) => {
      const result = await updateLandParcel(parcel.id, data as LandParcelUpdate);
      setUpdatedParcel(result);
      onSaved();
    },
    [parcel.id, onSaved],
  );

  return (
    <ModalShell title={`Edit — ${parcel.parcel_name}`} onClose={onClose} wide>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0, 1fr) minmax(240px, 280px)",
          gap: 24,
          alignItems: "start",
        }}
      >
        <LandParcelForm
          parcel={updatedParcel}
          onSave={handleSave}
          onCancel={onClose}
        />
        <div style={{ minWidth: 0 }}>
          <LandParcelMetricsPanel parcel={updatedParcel} />
        </div>
      </div>
    </ModalShell>
  );
}

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------

/**
 * Land inventory page — land parcel management dashboard.
 *
 * Shows KPI summary and a table of land parcels. Supports create,
 * edit (full structured form with grouped sections), status update,
 * and delete operations. Computed metrics remain display-only.
 */
export default function LandPage() {
  const [parcels, setParcels] = useState<LandParcel[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingParcel, setEditingParcel] = useState<LandParcel | null>(null);
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

  const handleSaved = useCallback(() => {
    setEditingParcel(null);
    fetchParcels();
  }, [fetchParcels]);

  const handleEdit = useCallback(
    async (parcelId: string) => {
      try {
        const fresh = await getLandParcel(parcelId);
        setEditingParcel(fresh);
      } catch (err: unknown) {
        setError(
          err instanceof Error ? err.message : "Failed to load parcel details.",
        );
      }
    },
    [],
  );

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
  const totalEffectiveBasis = parcels.reduce((sum, p) => sum + (p.effective_land_basis ?? 0), 0);

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
      {(totalAreaSqm > 0 || totalEffectiveBasis > 0) && (
        <div className={styles.kpiGrid3} style={{ marginBottom: "var(--space-6)" }}>
          {totalAreaSqm > 0 && (
            <MetricCard
              title="Total Land Area"
              value={`${totalAreaSqm.toLocaleString()} m²`}
            />
          )}
          {totalEffectiveBasis > 0 && (
            <MetricCard
              title="Total Effective Basis"
              value={formatCurrency(totalEffectiveBasis)}
            />
          )}
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
                <th>Effective Basis</th>
                <th>Gross /m²</th>
                <th>Buildable /m²</th>
                <th>Zoning</th>
                <th>Status</th>
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
                  <td
                    style={{
                      fontWeight: 500,
                      color:
                        parcel.effective_land_basis != null
                          ? "var(--color-text)"
                          : "var(--color-text-muted)",
                    }}
                  >
                    {formatCurrency(parcel.effective_land_basis, parcel.currency)}
                  </td>
                  <td
                    style={{
                      color:
                        parcel.gross_land_price_per_sqm != null
                          ? "var(--color-text)"
                          : "var(--color-text-muted)",
                    }}
                  >
                    {formatPerSqm(parcel.gross_land_price_per_sqm)}
                  </td>
                  <td
                    style={{
                      color:
                        parcel.effective_land_price_per_buildable_sqm != null
                          ? "var(--color-text)"
                          : "var(--color-text-muted)",
                    }}
                  >
                    {formatPerSqm(parcel.effective_land_price_per_buildable_sqm)}
                  </td>
                  <td>{parcel.zoning_category ?? "—"}</td>
                  <td>
                    <span
                      className={`${styles.badge} ${statusBadgeClass(parcel.status)}`}
                    >
                      {formatStatus(parcel.status)}
                    </span>
                  </td>
                  <td>
                    <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                      {/* Quick status change */}
                      <select
                        value={parcel.status}
                        onChange={(e) =>
                          handleStatusChange(
                            parcel.id,
                            e.target.value as LandStatus,
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
                        aria-label={`Change status for ${parcel.parcel_name}`}
                      >
                        <option value="draft">Draft</option>
                        <option value="under_review">Under Review</option>
                        <option value="approved">Approved</option>
                        <option value="archived">Archived</option>
                      </select>
                      {/* Edit button */}
                      <button
                        type="button"
                        onClick={() => handleEdit(parcel.id)}
                        style={{
                          padding: "4px 10px",
                          border: "1px solid var(--color-border)",
                          borderRadius: 4,
                          background: "var(--color-surface)",
                          color: "var(--color-text)",
                          cursor: "pointer",
                          fontSize: "0.8rem",
                        }}
                        aria-label={`Edit ${parcel.parcel_name}`}
                      >
                        Edit
                      </button>
                      {/* Delete button */}
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
                          cursor:
                            deletingId === parcel.id ? "not-allowed" : "pointer",
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

      {/* Edit modal */}
      {editingParcel && (
        <EditParcelModal
          parcel={editingParcel}
          onClose={() => setEditingParcel(null)}
          onSaved={handleSaved}
        />
      )}
    </PageContainer>
  );
}
