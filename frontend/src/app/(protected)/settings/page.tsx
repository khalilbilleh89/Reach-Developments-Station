import { PageContainer } from "@/components/shell/PageContainer";
import styles from "@/styles/demo-shell.module.css";

/**
 * Settings — executive demo placeholder.
 *
 * Shows structured settings category cards for management preview.
 *
 * INTENTIONAL DEMO DATA — this page displays non-wired placeholder content
 * for organisation-level settings (company profile, branding, users, roles)
 * which are not yet implemented as backend resources.
 *
 * Backend-implemented settings (pricing policies, commission policies, and
 * project templates) are accessible via the settings-api.ts wrapper
 * (frontend/src/lib/settings-api.ts → /api/v1/settings/*).
 * They will be surfaced in a dedicated settings management UI in a follow-up PR.
 */
export default function Page() {
  const settingsCategories = [
    {
      icon: "🏢",
      title: "Company Profile",
      desc: "Organisation name, trade licence details, registered address, and contact information.",
      items: [
        { label: "Company Name", value: "Reach Developments" },
        { label: "Trade Licence", value: "TL-2021-AUH-04821" },
        { label: "Base Currency", value: "AED" },
        { label: "Jurisdiction", value: "Abu Dhabi, UAE" },
      ],
    },
    {
      icon: "🎨",
      title: "Branding",
      desc: "Platform logo, primary colour, and white-label display settings.",
      items: [
        { label: "Logo", value: "reach-logo.svg" },
        { label: "Primary Colour", value: "#3b5bdb" },
        { label: "Sidebar Theme", value: "Dark (#1e2536)" },
        { label: "Report Watermark", value: "Enabled" },
      ],
    },
    {
      icon: "👥",
      title: "Users & Roles",
      desc: "Platform users, assigned roles, and access scopes per module.",
      items: [
        { label: "Total Users", value: "12 active" },
        { label: "Admin", value: "2 users" },
        { label: "Finance Manager", value: "3 users" },
        { label: "Sales Manager", value: "4 users" },
      ],
    },
    {
      icon: "🔐",
      title: "Permissions",
      desc: "Role-based access control matrix across all platform modules.",
      items: [
        { label: "Finance Module", value: "finance_manager, admin" },
        { label: "Commission Module", value: "sales_manager, admin" },
        { label: "Cashflow Module", value: "finance_manager, admin" },
        { label: "Settings Module", value: "admin only" },
      ],
    },
    {
      icon: "💱",
      title: "Currency & Defaults",
      desc: "Default currency, pricing precision, area units, and numeric display format.",
      items: [
        { label: "Display Currency", value: "AED" },
        { label: "Pricing Precision", value: "2 decimal places" },
        { label: "Area Unit", value: "sq ft" },
        { label: "Number Format", value: "1,234,567.00" },
      ],
    },
    {
      icon: "🔔",
      title: "Notification Preferences",
      desc: "System alerts, overdue payment notifications, and registration status updates.",
      items: [
        { label: "Overdue Alerts", value: "Email + In-app" },
        { label: "Registration Updates", value: "Email" },
        { label: "Commission Approvals", value: "In-app" },
        { label: "Daily Digest", value: "Disabled" },
      ],
    },
  ];

  return (
    <PageContainer
      title="Settings"
      subtitle="Application configuration and user preferences."
    >
      <div className={styles.demoBanner}>⬡ Demo Preview — static data only</div>

      <div className={styles.settingsGrid}>
        {settingsCategories.map((cat) => (
          <div key={cat.title} className={styles.settingsCard}>
            <div className={styles.settingsCardHeader}>
              <span className={styles.settingsCardIcon} aria-hidden="true">
                {cat.icon}
              </span>
              <span className={styles.settingsCardTitle}>{cat.title}</span>
            </div>
            <p className={styles.settingsCardDesc}>{cat.desc}</p>
            <div className={styles.settingsCardItems}>
              {cat.items.map((item) => (
                <div key={item.label} className={styles.settingsCardItem}>
                  <span className={styles.settingsCardItemLabel}>{item.label}</span>
                  <span className={styles.settingsCardItemValue}>{item.value}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </PageContainer>
  );
}
