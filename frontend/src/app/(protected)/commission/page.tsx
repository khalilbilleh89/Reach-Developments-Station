import { PageContainer } from "@/components/shell/PageContainer";
import { MetricCard } from "@/components/dashboard/MetricCard";
import { demoCommissionRows, type CommissionStatus } from "@/lib/demo-data";
import styles from "@/styles/demo-shell.module.css";

/**
 * Commission — executive demo placeholder.
 *
 * Shows commission payout queue, slab tier preview, and per-agent summary
 * using static demo data. Replace with live data in a follow-up commission PR.
 */
export default function Page() {
  function statusBadgeClass(status: CommissionStatus) {
    switch (status) {
      case "Paid":
        return styles.badgeGreen;
      case "Approved":
        return styles.badgeBlue;
      case "Pending":
        return styles.badgeYellow;
      case "Under Review":
        return styles.badgePurple;
      default:
        return styles.badgeGray;
    }
  }

  return (
    <PageContainer
      title="Commission"
      subtitle="Commission plans, slabs, and payout tracking."
    >
      <div className={styles.demoBanner}>⬡ Demo Preview — static data only</div>

      {/* KPI summary */}
      <div className={styles.kpiGrid}>
        <MetricCard
          title="Total Due"
          value="AED 876,250"
          subtitle="6 active commission records"
          icon="💰"
        />
        <MetricCard
          title="Paid"
          value="AED 245,000"
          subtitle="2 payouts processed"
          icon="✅"
        />
        <MetricCard
          title="Pending Approval"
          value="AED 432,500"
          subtitle="3 records awaiting sign-off"
          icon="⏳"
        />
        <MetricCard
          title="Under Review"
          value="AED 93,750"
          subtitle="1 record in dispute review"
          icon="🔍"
        />
      </div>

      {/* Commission slab tiers */}
      <div className={styles.sectionHeader}>
        <h2 className={styles.sectionTitle}>Commission Slab Preview</h2>
        <span className={styles.sectionNote}>Configurable tiers — demo data</span>
      </div>
      <div className={styles.slabGrid}>
        <div className={styles.slabCard}>
          <div className={styles.slabTier}>Standard</div>
          <div className={styles.slabRate}>2.0%</div>
          <div className={styles.slabDesc}>Post-launch / secondary market sales</div>
        </div>
        <div className={styles.slabCard}>
          <div className={styles.slabTier}>Premium</div>
          <div className={styles.slabRate}>2.5%</div>
          <div className={styles.slabDesc}>Primary launch &amp; preferred agency deals</div>
        </div>
        <div className={styles.slabCard}>
          <div className={styles.slabTier}>Incentive</div>
          <div className={styles.slabRate}>3.0%</div>
          <div className={styles.slabDesc}>Target achievement &amp; campaign top-up</div>
        </div>
      </div>

      {/* Payout table */}
      <div className={styles.sectionHeader}>
        <h2 className={styles.sectionTitle}>Commission Payout Queue</h2>
        <span className={styles.sectionNote}>
          {demoCommissionRows.length} records · Demo data
        </span>
      </div>
      <div className={styles.tableWrapper}>
        <table className={styles.table} aria-label="Commission payout queue">
          <thead>
            <tr>
              <th scope="col">Ref</th>
              <th scope="col">Agent</th>
              <th scope="col">Agency</th>
              <th scope="col">Unit</th>
              <th scope="col">Project</th>
              <th scope="col">Contract Value</th>
              <th scope="col">Rate</th>
              <th scope="col">Commission Due</th>
              <th scope="col">Status</th>
              <th scope="col">Due Date</th>
            </tr>
          </thead>
          <tbody>
            {demoCommissionRows.map((row) => (
              <tr key={row.ref}>
                <td style={{ fontFamily: "monospace", fontSize: "var(--font-size-xs)" }}>
                  {row.ref}
                </td>
                <td style={{ fontWeight: "var(--font-weight-medium)" }}>{row.agentName}</td>
                <td>{row.agencyName}</td>
                <td style={{ fontFamily: "monospace", fontSize: "var(--font-size-xs)" }}>
                  {row.unitRef}
                </td>
                <td>{row.projectName}</td>
                <td>{row.contractValue}</td>
                <td>{row.commissionRate}</td>
                <td style={{ fontWeight: "var(--font-weight-semibold)" }}>
                  {row.commissionDue}
                </td>
                <td>
                  <span className={`${styles.badge} ${statusBadgeClass(row.status)}`}>
                    {row.status}
                  </span>
                </td>
                <td>{row.dueDate}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </PageContainer>
  );
}
