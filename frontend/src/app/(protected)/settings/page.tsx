"use client";

import React, { useState, useEffect } from "react";
import { PageContainer } from "@/components/shell/PageContainer";
import {
  listPricingPolicies,
  listCommissionPolicies,
  listProjectTemplates,
} from "@/lib/settings-api";
import type {
  PricingPolicy,
  CommissionPolicy,
  ProjectTemplate,
} from "@/lib/settings-types";
import styles from "@/styles/demo-shell.module.css";

/**
 * Settings — governance configuration page.
 *
 * Live sections (from backend API):
 *   • Pricing Policies  → /api/v1/settings/pricing-policies
 *   • Commission Policies → /api/v1/settings/commission-policies
 *   • Project Templates  → /api/v1/settings/project-templates
 *
 * INTENTIONAL DEMO — the organisation-level cards below (Company Profile,
 * Branding, Users & Roles, Permissions, Currency & Defaults, Notifications)
 * are placeholder content for settings domains not yet backed by a backend
 * resource. They will be replaced in a follow-up PR when those resources are
 * implemented.
 */

/** Maximum number of records fetched per governance resource on load. */
const SETTINGS_PAGE_SIZE = 100;

export default function Page() {
  const [pricingPolicies, setPricingPolicies] = useState<PricingPolicy[]>([]);
  const [commissionPolicies, setCommissionPolicies] = useState<CommissionPolicy[]>([]);
  const [projectTemplates, setProjectTemplates] = useState<ProjectTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    setLoading(true);
    setError(null);
    Promise.all([
      listPricingPolicies({ limit: SETTINGS_PAGE_SIZE }),
      listCommissionPolicies({ limit: SETTINGS_PAGE_SIZE }),
      listProjectTemplates({ limit: SETTINGS_PAGE_SIZE }),
    ])
      .then(([pricing, commission, templates]) => {
        if (cancelled) return;
        setPricingPolicies(pricing.items);
        setCommissionPolicies(commission.items);
        setProjectTemplates(templates.items);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(
          err instanceof Error ? err.message : "Failed to load settings",
        );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  // ─── Organisation-level demo cards ────────────────────────────────────────
  // INTENTIONAL DEMO DATA — these categories are not yet backed by backend
  // resources. They remain as structured placeholders for visibility.
  const orgCategories = [
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
      subtitle="Governance configuration and application preferences."
    >
      {/* Global error banner */}
      {error && (
        <p role="alert" className={styles.errorBanner}>
          {error}
        </p>
      )}

      {/* ── Pricing Policies ─────────────────────────────────────────────── */}
      <div className={styles.sectionHeader}>
        <h2 className={styles.sectionTitle}>Pricing Policies</h2>
        <span role="status" className={styles.sectionNote}>
          {loading ? "Loading…" : `${pricingPolicies.length} record${pricingPolicies.length !== 1 ? "s" : ""}`}
        </span>
      </div>

      {!loading && !error && pricingPolicies.length === 0 && (
        <p className={styles.sectionNote}>No pricing policies configured.</p>
      )}

      {pricingPolicies.length > 0 && (
        <div className={styles.tableWrapper}>
          <table className={styles.table} aria-label="Pricing policies">
            <thead>
              <tr>
                <th scope="col">Name</th>
                <th scope="col">Currency</th>
                <th scope="col">Base Markup %</th>
                <th scope="col">Balcony Factor</th>
                <th scope="col">Parking Mode</th>
                <th scope="col">Storage Mode</th>
                <th scope="col">Default</th>
                <th scope="col">Active</th>
              </tr>
            </thead>
            <tbody>
              {pricingPolicies.map((policy) => (
                <tr key={policy.id}>
                  <td style={{ fontWeight: "var(--font-weight-medium)" }}>
                    {policy.name}
                  </td>
                  <td>{policy.currency}</td>
                  <td>{policy.base_markup_percent}%</td>
                  <td>{policy.balcony_price_factor}</td>
                  <td>{policy.parking_price_mode}</td>
                  <td>{policy.storage_price_mode}</td>
                  <td>
                    <span
                      className={`${styles.badge} ${policy.is_default ? styles.badgeBlue : styles.badgeGray}`}
                    >
                      {policy.is_default ? "Yes" : "No"}
                    </span>
                  </td>
                  <td>
                    <span
                      className={`${styles.badge} ${policy.is_active ? styles.badgeGreen : styles.badgeGray}`}
                    >
                      {policy.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Commission Policies ──────────────────────────────────────────── */}
      <div className={styles.sectionHeader}>
        <h2 className={styles.sectionTitle}>Commission Policies</h2>
        <span role="status" className={styles.sectionNote}>
          {loading ? "Loading…" : `${commissionPolicies.length} record${commissionPolicies.length !== 1 ? "s" : ""}`}
        </span>
      </div>

      {!loading && !error && commissionPolicies.length === 0 && (
        <p className={styles.sectionNote}>No commission policies configured.</p>
      )}

      {commissionPolicies.length > 0 && (
        <div className={styles.tableWrapper}>
          <table className={styles.table} aria-label="Commission policies">
            <thead>
              <tr>
                <th scope="col">Name</th>
                <th scope="col">Pool %</th>
                <th scope="col">Calculation Mode</th>
                <th scope="col">Default</th>
                <th scope="col">Active</th>
              </tr>
            </thead>
            <tbody>
              {commissionPolicies.map((policy) => (
                <tr key={policy.id}>
                  <td style={{ fontWeight: "var(--font-weight-medium)" }}>
                    {policy.name}
                  </td>
                  <td>{policy.pool_percent}%</td>
                  <td>{policy.calculation_mode}</td>
                  <td>
                    <span
                      className={`${styles.badge} ${policy.is_default ? styles.badgeBlue : styles.badgeGray}`}
                    >
                      {policy.is_default ? "Yes" : "No"}
                    </span>
                  </td>
                  <td>
                    <span
                      className={`${styles.badge} ${policy.is_active ? styles.badgeGreen : styles.badgeGray}`}
                    >
                      {policy.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Project Templates ────────────────────────────────────────────── */}
      <div className={styles.sectionHeader}>
        <h2 className={styles.sectionTitle}>Project Templates</h2>
        <span role="status" className={styles.sectionNote}>
          {loading ? "Loading…" : `${projectTemplates.length} record${projectTemplates.length !== 1 ? "s" : ""}`}
        </span>
      </div>

      {!loading && !error && projectTemplates.length === 0 && (
        <p className={styles.sectionNote}>No project templates configured.</p>
      )}

      {projectTemplates.length > 0 && (
        <div className={styles.tableWrapper}>
          <table className={styles.table} aria-label="Project templates">
            <thead>
              <tr>
                <th scope="col">Name</th>
                <th scope="col">Default Currency</th>
                <th scope="col">Pricing Policy</th>
                <th scope="col">Commission Policy</th>
                <th scope="col">Active</th>
              </tr>
            </thead>
            <tbody>
              {projectTemplates.map((template) => (
                <tr key={template.id}>
                  <td style={{ fontWeight: "var(--font-weight-medium)" }}>
                    {template.name}
                  </td>
                  <td>{template.default_currency}</td>
                  <td className={styles.monospaceCell}>
                    {template.default_pricing_policy_id ?? "—"}
                  </td>
                  <td className={styles.monospaceCell}>
                    {template.default_commission_policy_id ?? "—"}
                  </td>
                  <td>
                    <span
                      className={`${styles.badge} ${template.is_active ? styles.badgeGreen : styles.badgeGray}`}
                    >
                      {template.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Organisation settings (INTENTIONAL DEMO) ─────────────────────── */}
      {/* INTENTIONAL DEMO — the cards below (Company Profile, Branding, etc.)
          represent organisation-level settings that are not yet backed by a
          backend resource. They will be replaced when those domains are
          implemented in a follow-up PR. */}
      <div className={styles.sectionHeader} style={{ marginTop: "var(--space-8)" }}>
        <h2 className={styles.sectionTitle}>Organisation Settings</h2>
        <span className={styles.sectionNote}>Preview only — not yet persisted</span>
      </div>
      <div className={styles.settingsGrid}>
        {orgCategories.map((cat) => (
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
