"use client";

/**
 * ProjectPhasingRecommendationsPanel.tsx
 *
 * Per-project deterministic phasing and inventory-release recommendations panel (PR-V7-03).
 *
 * Displays:
 *  - Current active phase context
 *  - Current-phase release strategy recommendation with urgency badge
 *  - Next-phase readiness recommendation
 *  - Sold / available units and sell-through %
 *  - Confidence level and human-readable reason
 *
 * Design principles:
 *  - All recommendation values are sourced from the backend; no recomputation here.
 *  - Renders a safe null/loading/error state at each phase.
 *  - Color indicators: green = release/prepare, amber = maintain, red = hold/defer, gray = n/a.
 *
 * PR-V7-03 — Phasing Optimization Engine (Inventory Release & Stage-Gate Recommendations)
 */

import React, { useEffect, useRef, useState } from "react";
import { getProjectPhasingRecommendations } from "@/lib/phasing-optimization-api";
import type {
  CurrentPhaseRecommendation,
  NextPhaseRecommendation,
  ProjectPhasingRecommendationResponse,
  ReleaseUrgency,
} from "@/lib/phasing-optimization-types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function currentRecLabel(rec: CurrentPhaseRecommendation): string {
  if (rec === "release_more_inventory") return "Release More Inventory";
  if (rec === "maintain_current_release") return "Maintain Current Release";
  if (rec === "hold_current_inventory") return "Hold Inventory";
  if (rec === "delay_further_release") return "Delay Further Release";
  return "Insufficient Data";
}

function nextRecLabel(rec: NextPhaseRecommendation): string {
  if (rec === "prepare_next_phase") return "Prepare Next Phase";
  if (rec === "do_not_open_next_phase") return "Do Not Open Next Phase";
  if (rec === "defer_next_phase") return "Defer Next Phase";
  if (rec === "not_applicable") return "N/A";
  return "Insufficient Data";
}

function currentRecBadgeStyle(rec: CurrentPhaseRecommendation): React.CSSProperties {
  if (rec === "release_more_inventory")
    return {
      background: "#dcfce7",
      color: "#15803d",
      padding: "2px 8px",
      borderRadius: 12,
      fontSize: "0.75rem",
      fontWeight: 600,
    };
  if (rec === "maintain_current_release")
    return {
      background: "#e0f2fe",
      color: "#0369a1",
      padding: "2px 8px",
      borderRadius: 12,
      fontSize: "0.75rem",
      fontWeight: 600,
    };
  if (rec === "hold_current_inventory" || rec === "delay_further_release")
    return {
      background: "#fee2e2",
      color: "#b91c1c",
      padding: "2px 8px",
      borderRadius: 12,
      fontSize: "0.75rem",
      fontWeight: 600,
    };
  return {
    background: "var(--color-border)",
    color: "var(--color-text-muted)",
    padding: "2px 8px",
    borderRadius: 12,
    fontSize: "0.75rem",
    fontWeight: 600,
  };
}

function nextRecBadgeStyle(rec: NextPhaseRecommendation): React.CSSProperties {
  if (rec === "prepare_next_phase")
    return {
      background: "#dcfce7",
      color: "#15803d",
      padding: "2px 8px",
      borderRadius: 12,
      fontSize: "0.75rem",
      fontWeight: 600,
    };
  if (rec === "defer_next_phase")
    return {
      background: "#fee2e2",
      color: "#b91c1c",
      padding: "2px 8px",
      borderRadius: 12,
      fontSize: "0.75rem",
      fontWeight: 600,
    };
  if (rec === "do_not_open_next_phase")
    return {
      background: "#fef3c7",
      color: "#92400e",
      padding: "2px 8px",
      borderRadius: 12,
      fontSize: "0.75rem",
      fontWeight: 600,
    };
  return {
    background: "var(--color-border)",
    color: "var(--color-text-muted)",
    padding: "2px 8px",
    borderRadius: 12,
    fontSize: "0.75rem",
    fontWeight: 600,
  };
}

function urgencyBadgeStyle(urgency: ReleaseUrgency): React.CSSProperties {
  if (urgency === "high")
    return {
      background: "#fef3c7",
      color: "#92400e",
      padding: "2px 8px",
      borderRadius: 12,
      fontSize: "0.75rem",
      fontWeight: 600,
    };
  if (urgency === "medium")
    return {
      background: "#e0f2fe",
      color: "#0369a1",
      padding: "2px 8px",
      borderRadius: 12,
      fontSize: "0.75rem",
      fontWeight: 600,
    };
  if (urgency === "low")
    return {
      background: "var(--color-border)",
      color: "var(--color-text-muted)",
      padding: "2px 8px",
      borderRadius: 12,
      fontSize: "0.75rem",
      fontWeight: 600,
    };
  return {
    background: "var(--color-border)",
    color: "var(--color-text-muted)",
    padding: "2px 8px",
    borderRadius: 12,
    fontSize: "0.75rem",
    fontWeight: 600,
  };
}

function urgencyLabel(urgency: ReleaseUrgency): string {
  if (urgency === "high") return "High Urgency";
  if (urgency === "medium") return "Medium Urgency";
  if (urgency === "low") return "Low Urgency";
  return "No Urgency";
}

function confidenceLabel(confidence: "high" | "medium" | "low"): string {
  if (confidence === "high") return "High confidence";
  if (confidence === "medium") return "Medium confidence";
  return "Low confidence";
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

interface ProjectPhasingRecommendationsPanelProps {
  projectId: string;
}

export function ProjectPhasingRecommendationsPanel({
  projectId,
}: ProjectPhasingRecommendationsPanelProps) {
  const [data, setData] =
    useState<ProjectPhasingRecommendationResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setError(null);

    getProjectPhasingRecommendations(projectId, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) {
          setData(result);
          setLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (!controller.signal.aborted) {
          setError(
            err instanceof Error
              ? err.message
              : "Failed to load phasing recommendations.",
          );
          setLoading(false);
        }
      });

    return () => {
      controller.abort();
    };
  }, [projectId]);

  if (loading) {
    return (
      <div
        style={{ padding: "16px", color: "var(--color-text-muted)" }}
        data-testid="phasing-rec-loading"
      >
        Loading phasing recommendations…
      </div>
    );
  }

  if (error) {
    return (
      <div
        style={{ padding: "16px", color: "#b91c1c" }}
        data-testid="phasing-rec-error"
      >
        {error}
      </div>
    );
  }

  if (!data) return null;

  const isInsufficient =
    data.current_phase_recommendation === "insufficient_data";

  return (
    <div
      style={{
        background: "var(--color-surface)",
        border: "1px solid var(--color-border)",
        borderRadius: 8,
        padding: "20px",
        marginTop: 16,
      }}
      data-testid="phasing-recommendations-panel"
    >
      <h3
        style={{
          fontSize: "1rem",
          fontWeight: 600,
          margin: "0 0 4px",
          color: "var(--color-text)",
        }}
      >
        Phasing Recommendations
      </h3>
      <p
        style={{
          fontSize: "0.8125rem",
          color: "var(--color-text-muted)",
          margin: "0 0 16px",
        }}
      >
        Deterministic inventory-release and phase-progression guidance — recommendations only, no
        records mutated
      </p>

      {/* Current phase context */}
      {data.current_phase_name && (
        <div
          style={{
            padding: "10px 12px",
            background: "var(--color-background)",
            border: "1px solid var(--color-border)",
            borderRadius: 6,
            fontSize: "0.8125rem",
            color: "var(--color-text-muted)",
            marginBottom: 16,
          }}
          data-testid="current-phase-context"
        >
          Active phase: <strong style={{ color: "var(--color-text)" }}>{data.current_phase_name}</strong>
        </div>
      )}

      {/* Insufficient data state */}
      {isInsufficient ? (
        <p
          style={{
            fontSize: "0.875rem",
            color: "var(--color-text-muted)",
            fontStyle: "italic",
          }}
          data-testid="phasing-rec-insufficient"
        >
          {data.reason}
        </p>
      ) : (
        <>
          {/* Recommendation grid */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
              gap: 12,
              marginBottom: 16,
            }}
            data-testid="phasing-rec-grid"
          >
            {/* Current phase card */}
            <div
              style={{
                border: "1px solid var(--color-border)",
                borderRadius: 8,
                padding: "14px",
                background: "var(--color-background)",
              }}
              data-testid="current-phase-card"
            >
              <div
                style={{
                  fontSize: "0.75rem",
                  fontWeight: 600,
                  color: "var(--color-text-muted)",
                  textTransform: "uppercase",
                  letterSpacing: "0.05em",
                  marginBottom: 8,
                }}
              >
                Current Phase
              </div>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 8 }}>
                <span
                  style={currentRecBadgeStyle(data.current_phase_recommendation)}
                  data-testid="current-phase-badge"
                >
                  {currentRecLabel(data.current_phase_recommendation)}
                </span>
                {data.release_urgency !== "none" && (
                  <span
                    style={urgencyBadgeStyle(data.release_urgency)}
                    data-testid="urgency-badge"
                  >
                    {urgencyLabel(data.release_urgency)}
                  </span>
                )}
              </div>
              {/* Inventory stats */}
              <div
                style={{
                  display: "flex",
                  gap: 12,
                  fontSize: "0.8125rem",
                  color: "var(--color-text-muted)",
                  marginBottom: 8,
                  flexWrap: "wrap",
                }}
                data-testid="inventory-stats"
              >
                <span>{data.sold_units} sold</span>
                <span>{data.available_units} available</span>
                {data.sell_through_pct != null && (
                  <span>
                    <strong style={{ color: "var(--color-text)" }}>
                      {data.sell_through_pct.toFixed(1)}%
                    </strong>{" "}
                    sell-through
                  </span>
                )}
              </div>
              <div
                style={{
                  fontSize: "0.75rem",
                  color: "var(--color-text-muted)",
                }}
              >
                {confidenceLabel(data.confidence)}
              </div>
            </div>

            {/* Next phase card */}
            <div
              style={{
                border: "1px solid var(--color-border)",
                borderRadius: 8,
                padding: "14px",
                background: "var(--color-background)",
              }}
              data-testid="next-phase-card"
            >
              <div
                style={{
                  fontSize: "0.75rem",
                  fontWeight: 600,
                  color: "var(--color-text-muted)",
                  textTransform: "uppercase",
                  letterSpacing: "0.05em",
                  marginBottom: 8,
                }}
              >
                Next Phase
              </div>
              <span
                style={nextRecBadgeStyle(data.next_phase_recommendation)}
                data-testid="next-phase-badge"
              >
                {nextRecLabel(data.next_phase_recommendation)}
              </span>
              {data.next_phase_name && (
                <div
                  style={{
                    fontSize: "0.8125rem",
                    color: "var(--color-text-muted)",
                    marginTop: 8,
                  }}
                  data-testid="next-phase-name"
                >
                  {data.next_phase_name}
                </div>
              )}
              {!data.has_next_phase && (
                <div
                  style={{
                    fontSize: "0.8125rem",
                    color: "var(--color-text-muted)",
                    marginTop: 8,
                    fontStyle: "italic",
                  }}
                >
                  No next phase in project structure
                </div>
              )}
            </div>
          </div>

          {/* Reason / explanation */}
          <div
            style={{
              padding: "10px 12px",
              background: "var(--color-background)",
              border: "1px solid var(--color-border)",
              borderRadius: 6,
              fontSize: "0.8125rem",
              color: "var(--color-text-muted)",
              fontStyle: "italic",
            }}
            data-testid="phasing-reason"
          >
            {data.reason}
          </div>
        </>
      )}
    </div>
  );
}
