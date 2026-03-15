import { PageContainer } from "@/components/shell/PageContainer";
import { MetricCard } from "@/components/dashboard/MetricCard";
import { demoProjects } from "@/lib/demo-data";
import styles from "@/styles/demo-shell.module.css";

/**
 * Projects — executive demo placeholder.
 *
 * Displays static preview cards and KPIs using real-estate-shaped demo data.
 * Replace with live API data in PR-018 (Projects Module MVP).
 */
export default function Page() {
  const totalUnits = demoProjects.reduce((s, p) => s + p.totalUnits, 0);
  const totalSold = demoProjects.reduce((s, p) => s + p.sold, 0);
  const totalReserved = demoProjects.reduce((s, p) => s + p.reserved, 0);

  function phaseBadgeClass(phase: string) {
    switch (phase) {
      case "Construction":
        return styles.badgeBlue;
      case "Post-Handover":
        return styles.badgeGreen;
      case "Pre-Launch":
        return styles.badgeGray;
      case "Launch":
        return styles.badgePurple;
      default:
        return styles.badgeGray;
    }
  }

  return (
    <PageContainer
      title="Projects"
      subtitle="Manage and monitor all development projects."
      actions={
        <button type="button" className={styles.btnOutline} disabled aria-label="Create project (coming soon)">
          + Create Project
        </button>
      }
    >
      <div className={styles.demoBanner}>⬡ Demo Preview — static data only</div>

      {/* KPI summary */}
      <div className={styles.kpiGrid}>
        <MetricCard
          title="Active Projects"
          value={demoProjects.length}
          subtitle="Across Abu Dhabi &amp; Dubai"
          icon="📁"
        />
        <MetricCard
          title="Total Units"
          value={totalUnits}
          subtitle="All phases combined"
          icon="🏢"
        />
        <MetricCard
          title="Units Sold"
          value={totalSold}
          subtitle={`${Math.round((totalSold / totalUnits) * 100)}% sell-through`}
          icon="✅"
        />
        <MetricCard
          title="Units Reserved"
          value={totalReserved}
          subtitle="Pending contract execution"
          icon="📋"
        />
      </div>

      {/* Project cards grid */}
      <div className={styles.sectionHeader}>
        <h2 className={styles.sectionTitle}>Development Portfolio</h2>
        <span className={styles.sectionNote}>{demoProjects.length} projects · Demo data</span>
      </div>

      <div className={styles.projectGrid}>
        {demoProjects.map((project) => (
          <div key={project.id} className={styles.projectCard}>
            <div className={styles.projectCardHeader}>
              <div>
                <div className={styles.projectName}>{project.name}</div>
                <div className={styles.projectLocation}>📍 {project.location}</div>
              </div>
              <span className={`${styles.badge} ${phaseBadgeClass(project.phase)}`}>
                {project.phase}
              </span>
            </div>

            <div className={styles.projectStats}>
              <div className={styles.projectStat}>
                <div className={styles.projectStatLabel}>Available</div>
                <div className={styles.projectStatValue}>{project.available}</div>
              </div>
              <div className={styles.projectStat}>
                <div className={styles.projectStatLabel}>Reserved</div>
                <div className={styles.projectStatValue}>{project.reserved}</div>
              </div>
              <div className={styles.projectStat}>
                <div className={styles.projectStatLabel}>Sold</div>
                <div className={styles.projectStatValue}>{project.sold}</div>
              </div>
            </div>

            <div className={styles.projectFooter}>
              <span>Completion: {project.completionDate}</span>
              <span className={styles.projectRevenue}>{project.projectedRevenue}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Compact table summary */}
      <div className={styles.sectionHeader}>
        <h2 className={styles.sectionTitle}>Portfolio Summary</h2>
      </div>
      <div className={styles.tableWrapper}>
        <table className={styles.table} aria-label="Portfolio summary">
          <thead>
            <tr>
              <th scope="col">Project</th>
              <th scope="col">Location</th>
              <th scope="col">Phase</th>
              <th scope="col">Total Units</th>
              <th scope="col">Available</th>
              <th scope="col">Reserved</th>
              <th scope="col">Sold</th>
              <th scope="col">Proj. Revenue</th>
              <th scope="col">Completion</th>
            </tr>
          </thead>
          <tbody>
            {demoProjects.map((p) => (
              <tr key={p.id}>
                <td style={{ fontWeight: "var(--font-weight-medium)" }}>{p.name}</td>
                <td>{p.location}</td>
                <td>
                  <span className={`${styles.badge} ${phaseBadgeClass(p.phase)}`}>
                    {p.phase}
                  </span>
                </td>
                <td>{p.totalUnits}</td>
                <td>{p.available}</td>
                <td>{p.reserved}</td>
                <td>{p.sold}</td>
                <td>{p.projectedRevenue}</td>
                <td>{p.completionDate}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </PageContainer>
  );
}
