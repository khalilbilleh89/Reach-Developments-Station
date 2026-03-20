/**
 * demo-data.ts — UI-only static demo dataset for executive placeholder pages.
 *
 * ⚠️  These values are presentation-only. No backend records are created or
 * modified by this file. All data is hardcoded here and consumed exclusively
 * by the demo placeholder pages (Projects, Registry, Commission,
 * Cashflow, Settings).
 *
 * Replace with real API-driven data in follow-up module PRs (PR-018+).
 */

// ─── Projects ────────────────────────────────────────────────────────────────

export interface DemoProject {
  id: string;
  name: string;
  location: string;
  phase: string;
  totalUnits: number;
  available: number;
  reserved: number;
  sold: number;
  projectedRevenue: string;
  completionDate: string;
}

export const demoProjects: DemoProject[] = [
  {
    id: "P001",
    name: "Al Reem Residences",
    location: "Al Reem Island, Abu Dhabi",
    phase: "Construction",
    totalUnits: 240,
    available: 82,
    reserved: 48,
    sold: 110,
    projectedRevenue: "AED 1.24 B",
    completionDate: "Q4 2026",
  },
  {
    id: "P002",
    name: "Marina Bay Towers",
    location: "Dubai Marina, Dubai",
    phase: "Post-Handover",
    totalUnits: 180,
    available: 12,
    reserved: 8,
    sold: 160,
    projectedRevenue: "AED 980 M",
    completionDate: "Delivered",
  },
  {
    id: "P003",
    name: "Khalidiyah Gardens",
    location: "Khalidiyah, Abu Dhabi",
    phase: "Pre-Launch",
    totalUnits: 120,
    available: 120,
    reserved: 0,
    sold: 0,
    projectedRevenue: "AED 620 M",
    completionDate: "Q2 2028",
  },
  {
    id: "P004",
    name: "Saadiyat Grove",
    location: "Saadiyat Island, Abu Dhabi",
    phase: "Launch",
    totalUnits: 96,
    available: 64,
    reserved: 18,
    sold: 14,
    projectedRevenue: "AED 745 M",
    completionDate: "Q1 2027",
  },
];

// ─── Registry ─────────────────────────────────────────────────────────────────

export type RegistryStatus =
  | "Pending Submission"
  | "In Review"
  | "Approved"
  | "Missing Documents"
  | "Registered";

export interface DemoRegistryCase {
  caseRef: string;
  unitRef: string;
  projectName: string;
  buyerName: string;
  status: RegistryStatus;
  submittedDate: string;
  lastUpdated: string;
  missingDocs: number;
}

export const demoRegistryCases: DemoRegistryCase[] = [
  {
    caseRef: "REG-2024-001",
    unitRef: "ARR-B2-1204",
    projectName: "Al Reem Residences",
    buyerName: "Mohammed Al Mansoori",
    status: "In Review",
    submittedDate: "12 Feb 2026",
    lastUpdated: "01 Mar 2026",
    missingDocs: 0,
  },
  {
    caseRef: "REG-2024-002",
    unitRef: "MBT-T1-0508",
    projectName: "Marina Bay Towers",
    buyerName: "Sarah Al Hashimi",
    status: "Approved",
    submittedDate: "28 Jan 2026",
    lastUpdated: "15 Feb 2026",
    missingDocs: 0,
  },
  {
    caseRef: "REG-2024-003",
    unitRef: "ARR-B3-0712",
    projectName: "Al Reem Residences",
    buyerName: "Fatima Al Kaabi",
    status: "Missing Documents",
    submittedDate: "05 Feb 2026",
    lastUpdated: "10 Feb 2026",
    missingDocs: 2,
  },
  {
    caseRef: "REG-2024-004",
    unitRef: "SGR-A1-0301",
    projectName: "Saadiyat Grove",
    buyerName: "Khalid Al Shamsi",
    status: "Pending Submission",
    submittedDate: "—",
    lastUpdated: "08 Mar 2026",
    missingDocs: 3,
  },
  {
    caseRef: "REG-2024-005",
    unitRef: "MBT-T2-1105",
    projectName: "Marina Bay Towers",
    buyerName: "Aisha Al Zaabi",
    status: "Registered",
    submittedDate: "10 Nov 2025",
    lastUpdated: "02 Jan 2026",
    missingDocs: 0,
  },
  {
    caseRef: "REG-2024-006",
    unitRef: "ARR-B1-0905",
    projectName: "Al Reem Residences",
    buyerName: "Omar Al Rashidi",
    status: "In Review",
    submittedDate: "18 Feb 2026",
    lastUpdated: "05 Mar 2026",
    missingDocs: 1,
  },
  {
    caseRef: "REG-2024-007",
    unitRef: "SGR-B2-0210",
    projectName: "Saadiyat Grove",
    buyerName: "Noura Al Marzouqi",
    status: "Pending Submission",
    submittedDate: "—",
    lastUpdated: "12 Mar 2026",
    missingDocs: 4,
  },
];

// ─── Cashflow ─────────────────────────────────────────────────────────────────
// Removed in PR-2: cashflow page now fetches live data from cashflow-api.ts.
// Full demo layer removal is scheduled for PR-4.
