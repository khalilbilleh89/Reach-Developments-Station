/**
 * StrategyApprovalPanel tests (PR-V7-08)
 *
 * Validates:
 *  - loading state renders
 *  - error state renders
 *  - no-record state renders with request-approval button
 *  - approval record with pending status renders approve/reject buttons
 *  - approval record with approved status renders badge and audit meta
 *  - approval record with rejected status renders rejection reason
 *  - approved_at and approved_by_user_id rendered when present
 *  - rejection form shown on clicking reject button
 *  - rejection form hidden on cancel
 *  - confirm reject button disabled when rejection reason empty
 *  - new approval request button shown after resolution
 *  - no mutation controls shown for approved/rejected (only new-request)
 *  - null/missing optional fields render safely
 */

import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";

// Mock the API client
jest.mock("@/lib/strategy-approval-api", () => ({
  getLatestStrategyApproval: jest.fn(),
  createStrategyApproval: jest.fn(),
  approveStrategy: jest.fn(),
  rejectStrategy: jest.fn(),
}));

import {
  approveStrategy,
  createStrategyApproval,
  getLatestStrategyApproval,
  rejectStrategy,
} from "@/lib/strategy-approval-api";
import { StrategyApprovalPanel } from "@/components/strategy/StrategyApprovalPanel";
import type { StrategyApprovalResponse } from "@/lib/strategy-approval-types";

const mockGet = getLatestStrategyApproval as jest.MockedFunction<typeof getLatestStrategyApproval>;
const mockCreate = createStrategyApproval as jest.MockedFunction<typeof createStrategyApproval>;
const mockApprove = approveStrategy as jest.MockedFunction<typeof approveStrategy>;
const mockReject = rejectStrategy as jest.MockedFunction<typeof rejectStrategy>;

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const makePendingApproval = (): StrategyApprovalResponse => ({
  id: "approval-001",
  project_id: "proj-1",
  status: "pending",
  strategy_snapshot: { recommended_strategy: "maintain" },
  execution_package_snapshot: { execution_readiness: "ready_for_review" },
  approved_by_user_id: null,
  approved_at: null,
  rejection_reason: null,
  created_at: "2026-04-04T08:00:00Z",
  updated_at: "2026-04-04T08:00:00Z",
});

const makeApprovedApproval = (): StrategyApprovalResponse => ({
  id: "approval-002",
  project_id: "proj-1",
  status: "approved",
  strategy_snapshot: { recommended_strategy: "maintain" },
  execution_package_snapshot: { execution_readiness: "ready_for_review" },
  approved_by_user_id: "user-42",
  approved_at: "2026-04-04T09:00:00Z",
  rejection_reason: null,
  created_at: "2026-04-04T08:00:00Z",
  updated_at: "2026-04-04T09:00:00Z",
});

const makeRejectedApproval = (): StrategyApprovalResponse => ({
  id: "approval-003",
  project_id: "proj-1",
  status: "rejected",
  strategy_snapshot: { recommended_strategy: "maintain" },
  execution_package_snapshot: null,
  approved_by_user_id: null,
  approved_at: null,
  rejection_reason: "Market conditions unfavourable.",
  created_at: "2026-04-04T08:00:00Z",
  updated_at: "2026-04-04T08:30:00Z",
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("StrategyApprovalPanel", () => {
  afterEach(() => {
    jest.clearAllMocks();
  });

  it("renders loading state initially", () => {
    mockGet.mockReturnValue(new Promise(() => {})); // never resolves
    render(<StrategyApprovalPanel projectId="proj-1" />);
    expect(screen.getByTestId("approval-loading")).toBeInTheDocument();
  });

  it("renders error state when fetch fails", async () => {
    mockGet.mockRejectedValue(new Error("Network error"));
    render(<StrategyApprovalPanel projectId="proj-1" />);
    await waitFor(() => {
      expect(screen.getByTestId("approval-error")).toBeInTheDocument();
    });
    expect(screen.getByTestId("approval-error")).toHaveTextContent("Network error");
  });

  it("renders no-record state when null returned", async () => {
    mockGet.mockResolvedValue(null);
    render(<StrategyApprovalPanel projectId="proj-1" />);
    await waitFor(() => {
      expect(screen.getByTestId("approval-no-record")).toBeInTheDocument();
    });
    expect(screen.getByTestId("btn-request-approval")).toBeInTheDocument();
  });

  it("renders pending approval with approve and reject buttons", async () => {
    mockGet.mockResolvedValue(makePendingApproval());
    render(<StrategyApprovalPanel projectId="proj-1" />);
    await waitFor(() => {
      expect(screen.getByTestId("approval-panel")).toBeInTheDocument();
    });
    expect(screen.getByTestId("approval-status-badge")).toHaveTextContent("Pending Review");
    expect(screen.getByTestId("btn-approve")).toBeInTheDocument();
    expect(screen.getByTestId("btn-show-reject")).toBeInTheDocument();
  });

  it("renders approved status badge and audit meta", async () => {
    mockGet.mockResolvedValue(makeApprovedApproval());
    render(<StrategyApprovalPanel projectId="proj-1" />);
    await waitFor(() => {
      expect(screen.getByTestId("approval-status-badge")).toHaveTextContent("Approved");
    });
    expect(screen.getByTestId("approval-audit-meta")).toBeInTheDocument();
    expect(screen.getByTestId("approval-approved-by")).toHaveTextContent("user-42");
    expect(screen.getByTestId("approval-approved-at")).toBeInTheDocument();
  });

  it("renders rejected status with rejection reason", async () => {
    mockGet.mockResolvedValue(makeRejectedApproval());
    render(<StrategyApprovalPanel projectId="proj-1" />);
    await waitFor(() => {
      expect(screen.getByTestId("approval-status-badge")).toHaveTextContent("Rejected");
    });
    expect(screen.getByTestId("approval-rejection-reason")).toHaveTextContent(
      "Market conditions unfavourable.",
    );
  });

  it("shows rejection form when reject button clicked", async () => {
    mockGet.mockResolvedValue(makePendingApproval());
    render(<StrategyApprovalPanel projectId="proj-1" />);
    await waitFor(() => screen.getByTestId("btn-show-reject"));
    fireEvent.click(screen.getByTestId("btn-show-reject"));
    expect(screen.getByTestId("rejection-form")).toBeInTheDocument();
    expect(screen.getByTestId("rejection-reason-input")).toBeInTheDocument();
  });

  it("hides rejection form when cancel clicked", async () => {
    mockGet.mockResolvedValue(makePendingApproval());
    render(<StrategyApprovalPanel projectId="proj-1" />);
    await waitFor(() => screen.getByTestId("btn-show-reject"));
    fireEvent.click(screen.getByTestId("btn-show-reject"));
    expect(screen.getByTestId("rejection-form")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("btn-cancel-reject"));
    expect(screen.queryByTestId("rejection-form")).not.toBeInTheDocument();
  });

  it("confirm reject button is disabled when rejection reason is empty", async () => {
    mockGet.mockResolvedValue(makePendingApproval());
    render(<StrategyApprovalPanel projectId="proj-1" />);
    await waitFor(() => screen.getByTestId("btn-show-reject"));
    fireEvent.click(screen.getByTestId("btn-show-reject"));
    expect(screen.getByTestId("btn-confirm-reject")).toBeDisabled();
  });

  it("confirm reject button is enabled when rejection reason is provided", async () => {
    mockGet.mockResolvedValue(makePendingApproval());
    render(<StrategyApprovalPanel projectId="proj-1" />);
    await waitFor(() => screen.getByTestId("btn-show-reject"));
    fireEvent.click(screen.getByTestId("btn-show-reject"));
    fireEvent.change(screen.getByTestId("rejection-reason-input"), {
      target: { value: "Not yet ready." },
    });
    expect(screen.getByTestId("btn-confirm-reject")).not.toBeDisabled();
  });

  it("calls approveStrategy and updates state on approve", async () => {
    const pending = makePendingApproval();
    const approved = makeApprovedApproval();
    mockGet.mockResolvedValue(pending);
    mockApprove.mockResolvedValue(approved);
    render(<StrategyApprovalPanel projectId="proj-1" />);
    await waitFor(() => screen.getByTestId("btn-approve"));
    fireEvent.click(screen.getByTestId("btn-approve"));
    await waitFor(() => {
      expect(screen.getByTestId("approval-status-badge")).toHaveTextContent("Approved");
    });
    expect(mockApprove).toHaveBeenCalledWith(pending.id, {});
  });

  it("calls rejectStrategy and updates state on reject", async () => {
    const pending = makePendingApproval();
    const rejected = makeRejectedApproval();
    mockGet.mockResolvedValue(pending);
    mockReject.mockResolvedValue(rejected);
    render(<StrategyApprovalPanel projectId="proj-1" />);
    await waitFor(() => screen.getByTestId("btn-show-reject"));
    fireEvent.click(screen.getByTestId("btn-show-reject"));
    fireEvent.change(screen.getByTestId("rejection-reason-input"), {
      target: { value: "Market conditions unfavourable." },
    });
    fireEvent.click(screen.getByTestId("btn-confirm-reject"));
    await waitFor(() => {
      expect(screen.getByTestId("approval-status-badge")).toHaveTextContent("Rejected");
    });
    expect(mockReject).toHaveBeenCalledWith(pending.id, {
      rejection_reason: "Market conditions unfavourable.",
    });
  });

  it("shows new-request button after approval is resolved", async () => {
    mockGet.mockResolvedValue(makeApprovedApproval());
    render(<StrategyApprovalPanel projectId="proj-1" />);
    await waitFor(() => screen.getByTestId("approval-new-request"));
    expect(screen.getByTestId("btn-request-new-approval")).toBeInTheDocument();
  });

  it("shows new-request button after approval is rejected", async () => {
    mockGet.mockResolvedValue(makeRejectedApproval());
    render(<StrategyApprovalPanel projectId="proj-1" />);
    await waitFor(() => screen.getByTestId("approval-new-request"));
    expect(screen.getByTestId("btn-request-new-approval")).toBeInTheDocument();
  });

  it("calls createStrategyApproval with snapshots when requesting approval", async () => {
    mockGet.mockResolvedValue(null);
    mockCreate.mockResolvedValue(makePendingApproval());
    const snap = { recommended_strategy: "hold" };
    const pkgSnap = { execution_readiness: "caution_required" };
    render(
      <StrategyApprovalPanel
        projectId="proj-1"
        strategySnapshot={snap}
        executionPackageSnapshot={pkgSnap}
      />,
    );
    await waitFor(() => screen.getByTestId("btn-request-approval"));
    fireEvent.click(screen.getByTestId("btn-request-approval"));
    await waitFor(() => expect(mockCreate).toHaveBeenCalled());
    expect(mockCreate).toHaveBeenCalledWith(
      "proj-1",
      { strategy_snapshot: snap, execution_package_snapshot: pkgSnap },
    );
  });

  it("renders action error when approve fails", async () => {
    mockGet.mockResolvedValue(makePendingApproval());
    mockApprove.mockRejectedValue(new Error("Approval failed."));
    render(<StrategyApprovalPanel projectId="proj-1" />);
    await waitFor(() => screen.getByTestId("btn-approve"));
    fireEvent.click(screen.getByTestId("btn-approve"));
    await waitFor(() => {
      expect(screen.getByTestId("approval-action-error")).toBeInTheDocument();
    });
    expect(screen.getByTestId("approval-action-error")).toHaveTextContent("Approval failed.");
  });

  it("renders approval-id in audit meta", async () => {
    mockGet.mockResolvedValue(makePendingApproval());
    render(<StrategyApprovalPanel projectId="proj-1" />);
    await waitFor(() => screen.getByTestId("approval-id"));
    expect(screen.getByTestId("approval-id")).toHaveTextContent("approval-001");
  });
});
