"use client";

import React, { useEffect, useState } from "react";
import { PageContainer } from "@/components/shell/PageContainer";
import { PortfolioSummaryStrip } from "@/components/portfolio/PortfolioSummaryStrip";
import { PortfolioProjectCards } from "@/components/portfolio/PortfolioProjectCards";
import { PortfolioPipelinePanel } from "@/components/portfolio/PortfolioPipelinePanel";
import { PortfolioCollectionsPanel } from "@/components/portfolio/PortfolioCollectionsPanel";
import { PortfolioRiskFlagsPanel } from "@/components/portfolio/PortfolioRiskFlagsPanel";
import { PortfolioCostVariancePanel } from "@/components/portfolio/PortfolioCostVariancePanel";
import { getPortfolioDashboard } from "@/lib/portfolio-api";
import { getPortfolioCostVariance } from "@/lib/portfolio-variance-api";
import type { PortfolioDashboardResponse } from "@/lib/portfolio-types";
import type { PortfolioCostVarianceResponse } from "@/lib/portfolio-variance-types";
import styles from "@/styles/portfolio.module.css";

/**
 * Portfolio Dashboard page — executive portfolio intelligence view.
 *
 * Fetches the read-only portfolio dashboard and cost variance roll-up on
 * load and renders:
 *   - KPI summary strip (top-line portfolio metrics)
 *   - Project snapshot cards (per-project health and inventory)
 *   - Cost variance panel (portfolio construction cost variance roll-up)
 *   - Collections panel (overdue balance and collection rate)
 *   - Pipeline panel (scenarios and feasibility activity)
 *   - Risk flags panel (portfolio risk/alert signals)
 *
 * No portfolio metrics are computed here. All values are sourced from the
 * backend portfolio endpoints.
 */
export default function PortfolioPage() {
  const [data, setData] = useState<PortfolioDashboardResponse | null>(null);
  const [varianceData, setVarianceData] =
    useState<PortfolioCostVarianceResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    Promise.all([getPortfolioDashboard(), getPortfolioCostVariance()])
      .then(([dashboardResponse, varianceResponse]) => {
        setData(dashboardResponse);
        setVarianceData(varianceResponse);
      })
      .catch((err: unknown) => {
        setError(
          err instanceof Error ? err.message : "Failed to load portfolio dashboard.",
        );
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <PageContainer
      title="Portfolio"
      subtitle="Executive portfolio intelligence — live read from source data."
    >
      {loading ? (
        <div className={styles.loadingState}>Loading portfolio dashboard…</div>
      ) : error ? (
        <div className={styles.errorState} role="alert" aria-live="polite">
          {error}
        </div>
      ) : data?.summary.total_projects === 0 && data.projects.length === 0 ? (
        <div className={styles.emptyState}>
          <p className={styles.emptyStateTitle}>No portfolio data available.</p>
          <p className={styles.emptyStateBody}>
            Add projects and source data to populate the portfolio dashboard.
          </p>
        </div>
      ) : data ? (
        <div className={styles.sectionGrid}>
          <PortfolioSummaryStrip summary={data.summary} />
          <PortfolioProjectCards projects={data.projects} />
          {varianceData && (
            <PortfolioCostVariancePanel data={varianceData} />
          )}
          <PortfolioCollectionsPanel collections={data.collections} />
          <PortfolioPipelinePanel pipeline={data.pipeline} />
          <PortfolioRiskFlagsPanel riskFlags={data.risk_flags} />
        </div>
      ) : null}
    </PageContainer>
  );
}
