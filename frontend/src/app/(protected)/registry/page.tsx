import { PageContainer } from "@/components/shell/PageContainer";
import { MetricCard } from "@/components/dashboard/MetricCard";
import { demoRegistryCases, type RegistryStatus } from "@/lib/demo-data";
import styles from "@/styles/demo-shell.module.css";

/**
 * Registry — executive demo placeholder.
 *
 * Shows a conveyancing / title-transfer workflow tracker with per-unit
 * registration status. Replace with live data in a follow-up registry PR.
 */
export default function Page() {
  const counts = demoRegistryCases.reduce<Record<RegistryStatus, number>>(
    (acc, c) => {
      acc[c.status] = (acc[c.status] ?? 0) + 1;
      return acc;
    },
    {} as Record<RegistryStatus, number>,
  );

  function statusBadgeClass(status: RegistryStatus) {
    switch (status) {
      case "Registered":
        return styles.badgeGreen;
      case "Approved":
        return styles.badgeBlue;
      case "In Review":
        return styles.badgePurple;
      case "Missing Documents":
        return styles.badgeRed;
      case "Pending Submission":
        return styles.badgeYellow;
      default:
        return styles.badgeGray;
    }
  }

  return (
    <PageContainer
      title="Registry"
      subtitle="Conveyancing cases, milestones, and document tracking."
    >
      <div className={styles.demoBanner}>⬡ Demo Preview — static data only</div>

      {/* KPI summary */}
      <div className={styles.kpiGrid}>
        <MetricCard
          title="Pending Submission"
          value={counts["Pending Submission"] ?? 0}
          subtitle="Awaiting buyer documents"
          icon="⏳"
        />
        <MetricCard
          title="In Review"
          value={counts["In Review"] ?? 0}
          subtitle="Under authority processing"
          icon="🔍"
        />
        <MetricCard
          title="Approved"
          value={counts["Approved"] ?? 0}
          subtitle="Ready for title transfer"
          icon="✅"
        />
        <MetricCard
          title="Missing Docs"
          value={counts["Missing Documents"] ?? 0}
          subtitle="Requires buyer action"
          icon="⚠️"
        />
      </div>

      {/* Registration tracker table */}
      <div className={styles.sectionHeader}>
        <h2 className={styles.sectionTitle}>Registration Case Tracker</h2>
        <span className={styles.sectionNote}>
          {demoRegistryCases.length} cases · Demo data
        </span>
      </div>
      <div className={styles.tableWrapper}>
        <table className={styles.table} aria-label="Registration case tracker">
          <thead>
            <tr>
              <th scope="col">Case Ref</th>
              <th scope="col">Unit</th>
              <th scope="col">Project</th>
              <th scope="col">Buyer</th>
              <th scope="col">Status</th>
              <th scope="col">Submitted</th>
              <th scope="col">Last Updated</th>
              <th scope="col">Missing Docs</th>
            </tr>
          </thead>
          <tbody>
            {demoRegistryCases.map((c) => (
              <tr key={c.caseRef}>
                <td style={{ fontFamily: "monospace", fontSize: "var(--font-size-xs)" }}>
                  {c.caseRef}
                </td>
                <td style={{ fontFamily: "monospace", fontSize: "var(--font-size-xs)" }}>
                  {c.unitRef}
                </td>
                <td>{c.projectName}</td>
                <td>{c.buyerName}</td>
                <td>
                  <span className={`${styles.badge} ${statusBadgeClass(c.status)}`}>
                    {c.status}
                  </span>
                </td>
                <td>{c.submittedDate}</td>
                <td>{c.lastUpdated}</td>
                <td style={{ textAlign: "center" }}>
                  {c.missingDocs > 0 ? (
                    <span className={`${styles.badge} ${styles.badgeRed}`}>
                      {c.missingDocs}
                    </span>
                  ) : (
                    <span style={{ color: "var(--color-text-muted)" }}>—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </PageContainer>
  );
}
