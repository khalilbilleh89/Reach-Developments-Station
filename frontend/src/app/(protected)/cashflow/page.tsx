import { PageContainer } from "@/components/shell/PageContainer";
import { MetricCard } from "@/components/dashboard/MetricCard";
import { demoCashflowPeriods } from "@/lib/demo-data";
import styles from "@/styles/demo-shell.module.css";

/**
 * Cashflow — executive demo placeholder.
 *
 * Shows a monthly cashflow trend table and period KPIs using static demo data.
 * Replace with live forecasting data in a follow-up cashflow PR.
 */
export default function Page() {
  return (
    <PageContainer
      title="Cashflow"
      subtitle="Cashflow forecasting and period analysis."
    >
      <div className={styles.demoBanner}>⬡ Demo Preview — static data only</div>

      {/* KPI summary */}
      <div className={styles.kpiGrid}>
        <MetricCard
          title="YTD Inflows"
          value="AED 209.1 M"
          subtitle="Jan – Mar 2026 actual + projected"
          icon="📈"
          trend={{ label: "vs prior quarter", direction: "up" }}
        />
        <MetricCard
          title="YTD Outflows"
          value="AED 132.3 M"
          subtitle="Construction + overheads"
          icon="📉"
        />
        <MetricCard
          title="Net Cash Position"
          value="AED 76.8 M"
          subtitle="As of Mar 2026 (projected)"
          icon="💵"
          trend={{ label: "54.3% of inflows", direction: "neutral" }}
        />
        <MetricCard
          title="Funding Gap"
          value="AED 0"
          subtitle="No gap flagged this quarter"
          icon="🔒"
        />
      </div>

      {/* Alert card */}
      <div className={styles.alertCard}>
        <div className={styles.alertCardTitle}>⚠️ Dec 2025 Shortfall — Resolved</div>
        <div className={styles.alertCardBody}>
          A construction milestone payment in December 2025 created a temporary
          negative monthly position (– AED 9.6 M). The shortfall was covered by
          carry-forward reserves from Q3 and is not expected to recur in Q1 2026.
        </div>
      </div>

      {/* Monthly trend table */}
      <div className={styles.sectionHeader}>
        <h2 className={styles.sectionTitle}>Monthly Cashflow Trend</h2>
        <span className={styles.sectionNote}>Oct 2025 – Mar 2026 · Demo data</span>
      </div>
      <div className={styles.tableWrapper}>
        <table className={styles.table} aria-label="Monthly cashflow trend">
          <thead>
            <tr>
              <th scope="col">Period</th>
              <th scope="col">Total Inflows</th>
              <th scope="col">Total Outflows</th>
              <th scope="col">Net Position</th>
              <th scope="col">Status</th>
            </tr>
          </thead>
          <tbody>
            {demoCashflowPeriods.map((row) => (
              <tr key={row.period}>
                <td style={{ fontWeight: "var(--font-weight-medium)" }}>{row.period}</td>
                <td>{row.inflows}</td>
                <td>{row.outflows}</td>
                <td
                  className={
                    row.trend === "positive"
                      ? styles.trendPositive
                      : row.trend === "negative"
                        ? styles.trendNegative
                        : undefined
                  }
                >
                  {row.netPosition}
                </td>
                <td>
                  <span
                    className={`${styles.badge} ${
                      row.trend === "positive"
                        ? styles.badgeGreen
                        : row.trend === "negative"
                          ? styles.badgeRed
                          : styles.badgeGray
                    }`}
                  >
                    {row.trend === "positive"
                      ? "Surplus"
                      : row.trend === "negative"
                        ? "Shortfall"
                        : "Neutral"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </PageContainer>
  );
}
