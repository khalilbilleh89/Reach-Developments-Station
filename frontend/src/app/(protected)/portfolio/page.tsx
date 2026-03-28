"use client";

import React, { useEffect, useState } from "react";
import { PageContainer } from "@/components/shell/PageContainer";
import { PortfolioSummaryStrip } from "@/components/portfolio/PortfolioSummaryStrip";
import { PortfolioProjectCards } from "@/components/portfolio/PortfolioProjectCards";
import { PortfolioPipelinePanel } from "@/components/portfolio/PortfolioPipelinePanel";
import { PortfolioCollectionsPanel } from "@/components/portfolio/PortfolioCollectionsPanel";
import { PortfolioRiskFlagsPanel } from "@/components/portfolio/PortfolioRiskFlagsPanel";
import { PortfolioCostVariancePanel } from "@/components/portfolio/PortfolioCostVariancePanel";
import { PortfolioConstructionScorecardsPanel } from "@/components/portfolio/PortfolioConstructionScorecardsPanel";
import { PortfolioAbsorptionPanel } from "@/components/portfolio/PortfolioAbsorptionPanel";
import { getPortfolioDashboard } from "@/lib/portfolio-api";
import { getPortfolioCostVariance } from "@/lib/portfolio-variance-api";
import { getConstructionPortfolioScorecards } from "@/lib/construction-scorecard-api";
import { getPortfolioAbsorption } from "@/lib/portfolio-absorption-api";
import type { PortfolioDashboardResponse } from "@/lib/portfolio-types";
import type { PortfolioCostVarianceResponse } from "@/lib/portfolio-variance-types";
import type { ConstructionPortfolioScorecardsResponse } from "@/lib/construction-scorecard-types";
import type { PortfolioAbsorptionResponse } from "@/lib/portfolio-absorption-types";
import styles from "@/styles/portfolio.module.css";

/**
 * Portfolio Dashboard page — executive portfolio intelligence view.
 *
 * Fetches the read-only portfolio dashboard, cost variance roll-up,
 * construction health scorecards, and absorption intelligence on load
 * and renders:
 *   - KPI summary strip (top-line portfolio metrics)
 *   - Project snapshot cards (per-project health and inventory)
 *   - Portfolio absorption intelligence (PR-V7-01)
 *   - Construction health scorecards (baseline-vs-actual, PR-V6-14)
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
  const [constructionData, setConstructionData] =
    useState<ConstructionPortfolioScorecardsResponse | null>(null);
  const [absorptionData, setAbsorptionData] =
    useState<PortfolioAbsorptionResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    Promise.all([
      getPortfolioDashboard(),
      getPortfolioCostVariance(),
      getConstructionPortfolioScorecards(),
      getPortfolioAbsorption(),
    ])
      .then(([dashboardResponse, varianceResponse, constructionResponse, absorptionResponse]) => {
        setData(dashboardResponse);
        setVarianceData(varianceResponse);
        setConstructionData(constructionResponse);
        setAbsorptionData(absorptionResponse);
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
          {absorptionData && (
            <PortfolioAbsorptionPanel data={absorptionData} />
          )}
          {constructionData && (
            <PortfolioConstructionScorecardsPanel data={constructionData} />
          )}
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
