/**
 * StrategyExecutionPackagePanel tests (PR-V7-07)
 *
 * Validates:
 *  - loading state renders
 *  - error state renders
 *  - execution readiness badge renders correctly
 *  - summary text renders
 *  - action steps render with step numbers, titles, urgency, review flags
 *  - dependencies section renders cleared and blocked states
 *  - cautions section renders with severity
 *  - supporting metrics render
 *  - expected impact renders
 *  - read-only: no mutation controls
 *  - null/missing optional fields render safely
 */

import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";

// Mock the API client
jest.mock("@/lib/strategy-execution-package-api", () => ({
  getProjectStrategyExecutionPackage: jest.fn(),
}));

import { getProjectStrategyExecutionPackage } from "@/lib/strategy-execution-package-api";
import { StrategyExecutionPackagePanel } from "@/components/strategy/StrategyExecutionPackagePanel";
import type { ProjectStrategyExecutionPackageResponse } from "@/lib/strategy-execution-package-types";

const mockGetPackage = getProjectStrategyExecutionPackage as jest.MockedFunction<
  typeof getProjectStrategyExecutionPackage
>;

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const makeReadyPackage = (): ProjectStrategyExecutionPackageResponse => ({
  project_id: "proj-1",
  project_name: "Marina Tower",
  has_feasibility_baseline: true,
  recommended_strategy: "maintain",
  execution_readiness: "ready_for_review",
  summary: "Execution package for Marina Tower. Recommended: maintain release.",
  actions: [
    {
      step_number: 1,
      action_type: "simulation_review",
      action_title: "Review Simulation Evidence",
      action_description: "Review simulation output for the recommended strategy.",
      target_area: "review",
      urgency: "medium",
      depends_on: null,
      review_required: false,
    },
    {
      step_number: 2,
      action_type: "pricing_update_preparation",
      action_title: "Prepare Pricing Increase Package",
      action_description: "Prepare a pricing increase package of +5%.",
      target_area: "pricing",
      urgency: "medium",
      depends_on: null,
      review_required: true,
    },
  ],
  dependencies: [
    {
      dependency_type: "feasibility_baseline",
      dependency_label: "Feasibility Baseline",
      dependency_status: "cleared",
      blocking_reason: null,
    },
    {
      dependency_type: "strategy_data",
      dependency_label: "Strategy Data",
      dependency_status: "cleared",
      blocking_reason: null,
    },
  ],
  cautions: [],
  supporting_metrics: {
    best_irr: 0.15,
    risk_score: "medium",
    price_adjustment_pct: 5.0,
    phase_delay_months: 0,
    release_strategy: "maintain",
  },
  expected_impact: "Projected IRR: 15.00% (medium risk). Baseline available.",
  requires_manual_review: true,
});

const makeBlockedPackage = (): ProjectStrategyExecutionPackageResponse => ({
  project_id: "proj-2",
  project_name: "Palm Villa",
  has_feasibility_baseline: false,
  recommended_strategy: null,
  execution_readiness: "blocked_by_dependency",
  summary: "Execution package for Palm Villa. Blocked by missing baseline.",
  actions: [
    {
      step_number: 1,
      action_type: "baseline_dependency_review",
      action_title: "Establish Feasibility Baseline",
      action_description: "Create and approve a feasibility run.",
      target_area: "feasibility",
      urgency: "high",
      depends_on: null,
      review_required: true,
    },
  ],
  dependencies: [
    {
      dependency_type: "feasibility_baseline",
      dependency_label: "Feasibility Baseline",
      dependency_status: "blocked",
      blocking_reason: "No approved feasibility baseline exists.",
    },
    {
      dependency_type: "strategy_data",
      dependency_label: "Strategy Data",
      dependency_status: "cleared",
      blocking_reason: null,
    },
  ],
  cautions: [
    {
      severity: "high",
      caution_title: "Missing Feasibility Baseline",
      caution_description: "This project does not have an approved feasibility baseline.",
    },
  ],
  supporting_metrics: {
    best_irr: null,
    risk_score: null,
    price_adjustment_pct: null,
    phase_delay_months: null,
    release_strategy: null,
  },
  expected_impact: "Unable to estimate — no baseline.",
  requires_manual_review: true,
});

const makeCautionPackage = (): ProjectStrategyExecutionPackageResponse => ({
  project_id: "proj-3",
  project_name: "Downtown Hub",
  has_feasibility_baseline: true,
  recommended_strategy: "hold",
  execution_readiness: "caution_required",
  summary: "Execution package for Downtown Hub. Caution: high risk.",
  actions: [
    {
      step_number: 1,
      action_type: "simulation_review",
      action_title: "Review Simulation Evidence",
      action_description: "Review the high-risk simulation output.",
      target_area: "review",
      urgency: "high",
      depends_on: null,
      review_required: false,
    },
    {
      step_number: 2,
      action_type: "holdback_validation",
      action_title: "Validate Inventory Holdback",
      action_description: "Validate holdback cash flow.",
      target_area: "release",
      urgency: "medium",
      depends_on: null,
      review_required: true,
    },
    {
      step_number: 3,
      action_type: "executive_review",
      action_title: "Route for Executive Sign-Off",
      action_description: "High risk. Route for approval.",
      target_area: "review",
      urgency: "high",
      depends_on: null,
      review_required: true,
    },
  ],
  dependencies: [
    {
      dependency_type: "feasibility_baseline",
      dependency_label: "Feasibility Baseline",
      dependency_status: "cleared",
      blocking_reason: null,
    },
    {
      dependency_type: "strategy_data",
      dependency_label: "Strategy Data",
      dependency_status: "cleared",
      blocking_reason: null,
    },
  ],
  cautions: [
    {
      severity: "high",
      caution_title: "High-Risk Strategy",
      caution_description: "Executive sign-off required.",
    },
  ],
  supporting_metrics: {
    best_irr: 0.09,
    risk_score: "high",
    price_adjustment_pct: -5.0,
    phase_delay_months: 6,
    release_strategy: "hold",
  },
  expected_impact: "Projected IRR: 9.00% (high risk). Baseline available.",
  requires_manual_review: true,
});

// ---------------------------------------------------------------------------
// Loading state
// ---------------------------------------------------------------------------

test("renders loading state initially", () => {
  mockGetPackage.mockReturnValue(new Promise(() => {}));
  render(<StrategyExecutionPackagePanel projectId="proj-1" />);
  expect(screen.getByTestId("execution-package-panel")).toBeInTheDocument();
  expect(screen.getByText(/loading execution package/i)).toBeInTheDocument();
});

// ---------------------------------------------------------------------------
// Error state
// ---------------------------------------------------------------------------

test("renders error state on fetch failure", async () => {
  mockGetPackage.mockRejectedValue(new Error("Network error"));
  render(<StrategyExecutionPackagePanel projectId="proj-1" />);
  await waitFor(() => {
    expect(screen.getByTestId("execution-package-error")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Ready for review
// ---------------------------------------------------------------------------

test("renders execution readiness badge", async () => {
  mockGetPackage.mockResolvedValue(makeReadyPackage());
  render(<StrategyExecutionPackagePanel projectId="proj-1" />);
  await waitFor(() => {
    expect(screen.getByTestId("execution-readiness-badge")).toHaveTextContent(
      "Ready for Review",
    );
  });
});

test("renders summary text", async () => {
  mockGetPackage.mockResolvedValue(makeReadyPackage());
  render(<StrategyExecutionPackagePanel projectId="proj-1" />);
  await waitFor(() => {
    expect(screen.getByTestId("execution-package-summary")).toBeInTheDocument();
  });
});

test("renders action steps with sequential step numbers", async () => {
  mockGetPackage.mockResolvedValue(makeReadyPackage());
  render(<StrategyExecutionPackagePanel projectId="proj-1" />);
  await waitFor(() => {
    expect(screen.getByTestId("action-step-1")).toBeInTheDocument();
    expect(screen.getByTestId("action-step-2")).toBeInTheDocument();
  });
});

test("renders action step numbers in circles", async () => {
  mockGetPackage.mockResolvedValue(makeReadyPackage());
  render(<StrategyExecutionPackagePanel projectId="proj-1" />);
  await waitFor(() => {
    expect(screen.getByTestId("action-step-number-1")).toHaveTextContent("1");
    expect(screen.getByTestId("action-step-number-2")).toHaveTextContent("2");
  });
});

test("renders action titles", async () => {
  mockGetPackage.mockResolvedValue(makeReadyPackage());
  render(<StrategyExecutionPackagePanel projectId="proj-1" />);
  await waitFor(() => {
    expect(screen.getByTestId("action-title-1")).toHaveTextContent(
      "Review Simulation Evidence",
    );
    expect(screen.getByTestId("action-title-2")).toHaveTextContent(
      "Prepare Pricing Increase Package",
    );
  });
});

test("renders action urgency badges", async () => {
  mockGetPackage.mockResolvedValue(makeReadyPackage());
  render(<StrategyExecutionPackagePanel projectId="proj-1" />);
  await waitFor(() => {
    expect(screen.getByTestId("action-urgency-1")).toHaveTextContent("medium");
    expect(screen.getByTestId("action-urgency-2")).toHaveTextContent("medium");
  });
});

test("renders review-required flag when action needs review", async () => {
  mockGetPackage.mockResolvedValue(makeReadyPackage());
  render(<StrategyExecutionPackagePanel projectId="proj-1" />);
  await waitFor(() => {
    expect(screen.getByTestId("action-review-flag-2")).toHaveTextContent(
      "Review Required",
    );
  });
});

test("does not render review-required flag for non-review actions", async () => {
  mockGetPackage.mockResolvedValue(makeReadyPackage());
  render(<StrategyExecutionPackagePanel projectId="proj-1" />);
  await waitFor(() => {
    expect(screen.queryByTestId("action-review-flag-1")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Dependencies
// ---------------------------------------------------------------------------

test("renders dependencies section", async () => {
  mockGetPackage.mockResolvedValue(makeReadyPackage());
  render(<StrategyExecutionPackagePanel projectId="proj-1" />);
  await waitFor(() => {
    expect(screen.getByTestId("execution-dependencies-section")).toBeInTheDocument();
  });
});

test("renders cleared dependency status", async () => {
  mockGetPackage.mockResolvedValue(makeReadyPackage());
  render(<StrategyExecutionPackagePanel projectId="proj-1" />);
  await waitFor(() => {
    expect(screen.getByTestId("dep-status-feasibility_baseline")).toHaveTextContent(
      "Cleared",
    );
  });
});

test("renders blocked dependency status", async () => {
  mockGetPackage.mockResolvedValue(makeBlockedPackage());
  render(<StrategyExecutionPackagePanel projectId="proj-2" />);
  await waitFor(() => {
    expect(screen.getByTestId("dep-status-feasibility_baseline")).toHaveTextContent(
      "Blocked",
    );
  });
});

// ---------------------------------------------------------------------------
// Cautions
// ---------------------------------------------------------------------------

test("does not render cautions section when no cautions", async () => {
  mockGetPackage.mockResolvedValue(makeReadyPackage());
  render(<StrategyExecutionPackagePanel projectId="proj-1" />);
  await waitFor(() => {
    expect(
      screen.queryByTestId("execution-cautions-section"),
    ).not.toBeInTheDocument();
  });
});

test("renders cautions section when cautions present", async () => {
  mockGetPackage.mockResolvedValue(makeBlockedPackage());
  render(<StrategyExecutionPackagePanel projectId="proj-2" />);
  await waitFor(() => {
    expect(screen.getByTestId("execution-cautions-section")).toBeInTheDocument();
  });
});

test("renders high-risk caution for caution package", async () => {
  mockGetPackage.mockResolvedValue(makeCautionPackage());
  render(<StrategyExecutionPackagePanel projectId="proj-3" />);
  await waitFor(() => {
    expect(screen.getByText("High-Risk Strategy")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Supporting metrics
// ---------------------------------------------------------------------------

test("renders supporting metrics section", async () => {
  mockGetPackage.mockResolvedValue(makeReadyPackage());
  render(<StrategyExecutionPackagePanel projectId="proj-1" />);
  await waitFor(() => {
    expect(screen.getByTestId("execution-metrics-section")).toBeInTheDocument();
  });
});

test("renders best IRR in metrics", async () => {
  mockGetPackage.mockResolvedValue(makeReadyPackage());
  render(<StrategyExecutionPackagePanel projectId="proj-1" />);
  await waitFor(() => {
    expect(screen.getByTestId("execution-best-irr")).toHaveTextContent("15.00%");
  });
});

test("renders dash for null IRR in metrics", async () => {
  mockGetPackage.mockResolvedValue(makeBlockedPackage());
  render(<StrategyExecutionPackagePanel projectId="proj-2" />);
  await waitFor(() => {
    expect(screen.getByTestId("execution-best-irr")).toHaveTextContent("—");
  });
});

test("renders risk score in metrics", async () => {
  mockGetPackage.mockResolvedValue(makeReadyPackage());
  render(<StrategyExecutionPackagePanel projectId="proj-1" />);
  await waitFor(() => {
    expect(screen.getByTestId("execution-risk-score")).toHaveTextContent("medium");
  });
});

test("renders release strategy in metrics", async () => {
  mockGetPackage.mockResolvedValue(makeReadyPackage());
  render(<StrategyExecutionPackagePanel projectId="proj-1" />);
  await waitFor(() => {
    expect(screen.getByTestId("execution-release-strategy")).toHaveTextContent("maintain");
  });
});

// ---------------------------------------------------------------------------
// Expected impact
// ---------------------------------------------------------------------------

test("renders expected impact section", async () => {
  mockGetPackage.mockResolvedValue(makeReadyPackage());
  render(<StrategyExecutionPackagePanel projectId="proj-1" />);
  await waitFor(() => {
    expect(screen.getByTestId("execution-expected-impact")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Blocked execution readiness
// ---------------------------------------------------------------------------

test("renders blocked readiness badge", async () => {
  mockGetPackage.mockResolvedValue(makeBlockedPackage());
  render(<StrategyExecutionPackagePanel projectId="proj-2" />);
  await waitFor(() => {
    expect(screen.getByTestId("execution-readiness-badge")).toHaveTextContent("Blocked");
  });
});

// ---------------------------------------------------------------------------
// Caution required execution readiness
// ---------------------------------------------------------------------------

test("renders caution-required readiness badge", async () => {
  mockGetPackage.mockResolvedValue(makeCautionPackage());
  render(<StrategyExecutionPackagePanel projectId="proj-3" />);
  await waitFor(() => {
    expect(screen.getByTestId("execution-readiness-badge")).toHaveTextContent(
      "Caution Required",
    );
  });
});

test("renders executive review as last action for high-risk package", async () => {
  mockGetPackage.mockResolvedValue(makeCautionPackage());
  render(<StrategyExecutionPackagePanel projectId="proj-3" />);
  await waitFor(() => {
    expect(screen.getByTestId("action-title-3")).toHaveTextContent(
      "Route for Executive Sign-Off",
    );
  });
});

// ---------------------------------------------------------------------------
// Read-only: no mutation controls
// ---------------------------------------------------------------------------

test("renders no buttons that would mutate data", async () => {
  mockGetPackage.mockResolvedValue(makeReadyPackage());
  render(<StrategyExecutionPackagePanel projectId="proj-1" />);
  await waitFor(() => {
    expect(screen.getByTestId("execution-package-panel")).toBeInTheDocument();
  });
  const buttons = screen.queryAllByRole("button");
  expect(buttons.length).toBe(0);
});
