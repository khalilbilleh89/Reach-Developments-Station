/**
 * ProjectLifecycleSummaryPanel tests — validates rendering across loading,
 * error, blocked, and lifecycle stage states.
 */
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";

// Mock Next.js Link
jest.mock("next/link", () => {
  const MockLink = ({
    href,
    children,
    ...props
  }: {
    href: string;
    children: React.ReactNode;
    [key: string]: unknown;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  );
  MockLink.displayName = "MockLink";
  return MockLink;
});

// Mock CSS module
jest.mock("@/styles/projects.module.css", () => ({
  loadingText: "loadingText",
  errorBanner: "errorBanner",
  lifecyclePanel: "lifecyclePanel",
  lifecycleStageHeader: "lifecycleStageHeader",
  lifecycleStageInfo: "lifecycleStageInfo",
  lifecycleStageName: "lifecycleStageName",
  lifecycleStageProgress: "lifecycleStageProgress",
  lifecycleProgressBar: "lifecycleProgressBar",
  lifecycleProgressFill: "lifecycleProgressFill",
  lifecycleFlagsGrid: "lifecycleFlagsGrid",
  lifecycleFlagRow: "lifecycleFlagRow",
  lifecycleFlagPresent: "lifecycleFlagPresent",
  lifecycleFlagMissing: "lifecycleFlagMissing",
  lifecycleFlagLabel: "lifecycleFlagLabel",
  lifecycleFlagCount: "lifecycleFlagCount",
  lifecycleBlockedBanner: "lifecycleBlockedBanner",
  lifecycleNextStep: "lifecycleNextStep",
  lifecycleNextStepText: "lifecycleNextStepText",
  lifecycleNextStepCta: "lifecycleNextStepCta",
}));

// Mock API
jest.mock("@/lib/projects-api", () => ({
  getProjectLifecycleSummary: jest.fn(),
}));

import { getProjectLifecycleSummary } from "@/lib/projects-api";
import { ProjectLifecycleSummaryPanel } from "@/components/projects/ProjectLifecycleSummaryPanel";
import type { ProjectLifecycleSummary } from "@/lib/projects-types";

const mockGet = getProjectLifecycleSummary as jest.Mock;

// ---------------------------------------------------------------------------
// Factory helpers
// ---------------------------------------------------------------------------

const makeLandDefinedSummary = (): ProjectLifecycleSummary => ({
  project_id: "proj-1",
  has_scenarios: false,
  has_active_scenario: false,
  has_feasibility_runs: false,
  has_calculated_feasibility: false,
  has_phases: false,
  has_construction_records: false,
  has_approved_tender_baseline: false,
  scenario_count: 0,
  feasibility_run_count: 0,
  construction_record_count: 0,
  current_stage: "land_defined",
  recommended_next_step: "Create a development scenario to begin planning.",
  next_step_route: "/scenarios",
  blocked_reason: null,
  last_updated_at: "2024-01-15T10:00:00Z",
});

const makeConstructionBaselinePendingSummary = (): ProjectLifecycleSummary => ({
  project_id: "proj-2",
  has_scenarios: true,
  has_active_scenario: false,
  has_feasibility_runs: true,
  has_calculated_feasibility: true,
  has_phases: true,
  has_construction_records: true,
  has_approved_tender_baseline: false,
  scenario_count: 2,
  feasibility_run_count: 3,
  construction_record_count: 5,
  current_stage: "construction_baseline_pending",
  recommended_next_step: "Approve a tender baseline to unlock construction monitoring.",
  next_step_route: "/projects/proj-2/tender-comparisons",
  blocked_reason: "No approved tender baseline exists for this project.",
  last_updated_at: "2024-02-20T15:30:00Z",
});

const makeConstructionMonitoredSummary = (): ProjectLifecycleSummary => ({
  project_id: "proj-3",
  has_scenarios: true,
  has_active_scenario: true,
  has_feasibility_runs: true,
  has_calculated_feasibility: true,
  has_phases: true,
  has_construction_records: true,
  has_approved_tender_baseline: true,
  scenario_count: 1,
  feasibility_run_count: 2,
  construction_record_count: 8,
  current_stage: "construction_monitored",
  recommended_next_step: "View construction scorecard to monitor project health.",
  next_step_route: "/projects/proj-3/construction-costs",
  blocked_reason: null,
  last_updated_at: "2024-03-10T09:00:00Z",
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ProjectLifecycleSummaryPanel", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders loading state initially", () => {
    mockGet.mockReturnValue(new Promise(() => {}));
    render(<ProjectLifecycleSummaryPanel projectId="proj-1" />);
    expect(screen.getByText(/loading lifecycle summary/i)).toBeInTheDocument();
  });

  it("renders error state on fetch failure", async () => {
    mockGet.mockRejectedValue(new Error("Network error"));
    render(<ProjectLifecycleSummaryPanel projectId="proj-1" />);
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("Network error");
    });
  });

  it("renders land_defined stage with correct label", async () => {
    mockGet.mockResolvedValue(makeLandDefinedSummary());
    render(<ProjectLifecycleSummaryPanel projectId="proj-1" />);
    await waitFor(() => {
      expect(screen.getByText("Land Defined")).toBeInTheDocument();
    });
  });

  it("renders lifecycle progress percentage", async () => {
    mockGet.mockResolvedValue(makeLandDefinedSummary());
    render(<ProjectLifecycleSummaryPanel projectId="proj-1" />);
    await waitFor(() => {
      expect(screen.getByText(/13% complete/i)).toBeInTheDocument();
    });
  });

  it("renders recommended next step text", async () => {
    mockGet.mockResolvedValue(makeLandDefinedSummary());
    render(<ProjectLifecycleSummaryPanel projectId="proj-1" />);
    await waitFor(() => {
      expect(
        screen.getByText(/create a development scenario/i)
      ).toBeInTheDocument();
    });
  });

  it("renders next step CTA link with correct href", async () => {
    mockGet.mockResolvedValue(makeLandDefinedSummary());
    render(<ProjectLifecycleSummaryPanel projectId="proj-1" />);
    await waitFor(() => {
      const link = screen.getByRole("link", { name: /continue/i });
      expect(link).toHaveAttribute("href", "/scenarios");
    });
  });

  it("renders blocked banner when blocked_reason is present", async () => {
    mockGet.mockResolvedValue(makeConstructionBaselinePendingSummary());
    render(<ProjectLifecycleSummaryPanel projectId="proj-2" />);
    await waitFor(() => {
      const alert = screen.getByRole("alert");
      expect(alert).toHaveTextContent(
        "No approved tender baseline exists for this project."
      );
    });
  });

  it("does not render blocked banner when blocked_reason is null", async () => {
    mockGet.mockResolvedValue(makeConstructionMonitoredSummary());
    render(<ProjectLifecycleSummaryPanel projectId="proj-3" />);
    await waitFor(() => {
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    });
  });

  it("renders construction_monitored stage correctly", async () => {
    mockGet.mockResolvedValue(makeConstructionMonitoredSummary());
    render(<ProjectLifecycleSummaryPanel projectId="proj-3" />);
    await waitFor(() => {
      expect(screen.getByText("Construction Monitored")).toBeInTheDocument();
    });
  });

  it("renders flag counts for modules with records", async () => {
    mockGet.mockResolvedValue(makeConstructionBaselinePendingSummary());
    render(<ProjectLifecycleSummaryPanel projectId="proj-2" />);
    await waitFor(() => {
      // construction_record_count = 5
      expect(screen.getByText("5")).toBeInTheDocument();
    });
  });

  it("passes projectId to the API call", async () => {
    mockGet.mockResolvedValue(makeLandDefinedSummary());
    render(<ProjectLifecycleSummaryPanel projectId="proj-xyz" />);
    await waitFor(() => {
      expect(mockGet).toHaveBeenCalledWith("proj-xyz", expect.any(AbortSignal));
    });
  });

  it("renders a progress bar with correct aria attributes", async () => {
    mockGet.mockResolvedValue(makeLandDefinedSummary());
    render(<ProjectLifecycleSummaryPanel projectId="proj-1" />);
    await waitFor(() => {
      const bar = screen.getByRole("progressbar");
      expect(bar).toHaveAttribute("aria-valuenow", "13");
      expect(bar).toHaveAttribute("aria-valuemin", "0");
      expect(bar).toHaveAttribute("aria-valuemax", "100");
    });
  });
});
