/**
 * TenderComparisonClient tests
 *
 * Covers:
 *  - loading state on initial render
 *  - error state when list fetch fails
 *  - empty state when no comparison sets exist
 *  - set list renders after successful load
 *  - selecting a set triggers detail load
 *  - rapid selection switching: only the latest selection's detail wins
 *  - stale response from a superseded request does not overwrite current state
 *  - aborted/superseded error does not surface as user-facing error banner
 *  - PR-V6-13: approve-baseline button shown for non-approved set
 *  - PR-V6-13: approve-baseline button absent for already-approved set
 *  - PR-V6-13: confirmation modal opens on approve button click
 *  - PR-V6-13: modal cancel closes without calling API
 *  - PR-V6-13: confirming approval calls approveTenderBaseline
 *  - PR-V6-13: approved baseline badge shown in detail header
 *  - PR-V6-13: baseline metadata strip shown when approved
 */
import React from "react";
import { render, screen, waitFor, fireEvent, act } from "@testing-library/react";
import "@testing-library/jest-dom";

jest.mock("next/navigation", () => ({
  useParams: jest.fn(() => ({ id: "proj-1" })),
  useRouter: () => ({ push: jest.fn() }),
  usePathname: () => "/projects/proj-1/tender-comparisons",
}));

jest.mock("@/styles/construction.module.css", () => ({}));
jest.mock("@/components/shell/PageContainer.module.css", () => ({}));

jest.mock("@/lib/tender-comparison-api", () => ({
  listProjectTenderComparisons: jest.fn(),
  createTenderComparison: jest.fn(),
  getTenderComparison: jest.fn(),
  updateTenderComparison: jest.fn(),
  getTenderComparisonSummary: jest.fn(),
  createComparisonLine: jest.fn(),
  updateComparisonLine: jest.fn(),
  deleteComparisonLine: jest.fn(),
  approveTenderBaseline: jest.fn(),
}));

import { useParams } from "next/navigation";
import {
  listProjectTenderComparisons,
  getTenderComparison,
  getTenderComparisonSummary,
  approveTenderBaseline,
} from "@/lib/tender-comparison-api";
import { TenderComparisonClient } from "@/app/(protected)/projects/[id]/tender-comparisons/TenderComparisonClient";

const mockUseParams = useParams as jest.Mock;
const mockList = listProjectTenderComparisons as jest.Mock;
const mockGetSet = getTenderComparison as jest.Mock;
const mockGetSummary = getTenderComparisonSummary as jest.Mock;
const mockApprove = approveTenderBaseline as jest.Mock;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const makeSetItem = (
  id: string,
  title: string,
  overrides: Record<string, unknown> = {},
) => ({
  id,
  project_id: "proj-1",
  title,
  comparison_stage: "baseline_vs_tender" as const,
  baseline_label: "Baseline",
  comparison_label: "Tender",
  notes: null,
  is_active: true,
  is_approved_baseline: false,
  approved_at: null,
  approved_by_user_id: null,
  created_at: "2026-03-01T00:00:00Z",
  updated_at: "2026-03-01T00:00:00Z",
  ...overrides,
});

const makeFullSet = (
  id: string,
  title: string,
  overrides: Record<string, unknown> = {},
) => ({
  ...makeSetItem(id, title, overrides),
  lines: [],
});

const makeSummary = (setId: string) => ({
  comparison_set_id: setId,
  project_id: "proj-1",
  line_count: 0,
  total_baseline: "0.00",
  total_comparison: "0.00",
  total_variance: "0.00",
  total_variance_pct: null,
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

beforeEach(() => {
  jest.clearAllMocks();
  mockUseParams.mockReturnValue({ id: "proj-1" });
});

describe("TenderComparisonClient", () => {
  it("shows loading state while list is loading", () => {
    mockList.mockReturnValue(new Promise(() => {})); // never resolves
    render(<TenderComparisonClient />);
    expect(screen.getByTestId("loading-state")).toBeInTheDocument();
  });

  it("shows error state when list fetch fails", async () => {
    mockList.mockRejectedValue(new Error("Network failure"));
    render(<TenderComparisonClient />);
    await waitFor(() => {
      expect(screen.getByTestId("error-state")).toBeInTheDocument();
      expect(screen.getByText("Network failure")).toBeInTheDocument();
    });
  });

  it("shows empty state when no comparison sets exist", async () => {
    mockList.mockResolvedValue({ total: 0, items: [] });
    render(<TenderComparisonClient />);
    await waitFor(() => {
      expect(screen.getByTestId("sets-empty-state")).toBeInTheDocument();
    });
  });

  it("renders comparison set list after successful load", async () => {
    mockList.mockResolvedValue({
      total: 1,
      items: [makeSetItem("set-1", "Q1 Comparison")],
    });
    render(<TenderComparisonClient />);
    await waitFor(() => {
      expect(screen.getByText("Q1 Comparison")).toBeInTheDocument();
    });
  });

  it("shows detail loading state when a set is selected", async () => {
    mockList.mockResolvedValue({
      total: 1,
      items: [makeSetItem("set-1", "Q1 Comparison")],
    });
    // detail never resolves — stays in loading state
    mockGetSet.mockReturnValue(new Promise(() => {}));
    mockGetSummary.mockReturnValue(new Promise(() => {}));

    render(<TenderComparisonClient />);
    await waitFor(() =>
      expect(screen.getByText("Q1 Comparison")).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByLabelText("Open comparison set: Q1 Comparison"));
    await waitFor(() => {
      expect(screen.getByTestId("detail-loading-state")).toBeInTheDocument();
    });
  });

  it("shows set detail after selection resolves", async () => {
    mockList.mockResolvedValue({
      total: 1,
      items: [makeSetItem("set-1", "Q1 Comparison")],
    });
    mockGetSet.mockResolvedValue(makeFullSet("set-1", "Q1 Comparison"));
    mockGetSummary.mockResolvedValue(makeSummary("set-1"));

    render(<TenderComparisonClient />);
    await waitFor(() =>
      expect(screen.getByText("Q1 Comparison")).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByLabelText("Open comparison set: Q1 Comparison"));
    await waitFor(() => {
      expect(screen.getByTestId("lines-empty-state")).toBeInTheDocument();
    });
  });

  it("shows error when detail fetch fails", async () => {
    mockList.mockResolvedValue({
      total: 1,
      items: [makeSetItem("set-1", "Q1 Comparison")],
    });
    mockGetSet.mockRejectedValue(new Error("Detail fetch failed"));
    mockGetSummary.mockRejectedValue(new Error("Detail fetch failed"));

    render(<TenderComparisonClient />);
    await waitFor(() =>
      expect(screen.getByText("Q1 Comparison")).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByLabelText("Open comparison set: Q1 Comparison"));
    await waitFor(() => {
      expect(screen.getByTestId("detail-error-state")).toBeInTheDocument();
    });
  });

  it("rapid switching: only latest selection's detail is committed to state", async () => {
    mockList.mockResolvedValue({
      total: 2,
      items: [
        makeSetItem("set-1", "First Set"),
        makeSetItem("set-2", "Second Set"),
      ],
    });

    // set-1 detail resolves slowly; set-2 resolves immediately
    let resolveSet1: (v: unknown) => void;
    const set1Promise = new Promise((resolve) => {
      resolveSet1 = resolve;
    });

    mockGetSet.mockImplementation((id: string) => {
      if (id === "set-1") return set1Promise;
      return Promise.resolve(makeFullSet("set-2", "Second Set"));
    });
    mockGetSummary.mockImplementation((id: string) => {
      if (id === "set-1") return set1Promise;
      return Promise.resolve(makeSummary("set-2"));
    });

    render(<TenderComparisonClient />);
    await waitFor(() =>
      expect(screen.getByText("First Set")).toBeInTheDocument(),
    );

    // Click set-1 first (slow)
    fireEvent.click(screen.getByLabelText("Open comparison set: First Set"));

    // Immediately click set-2 (fast) — this becomes the latest selection
    fireEvent.click(screen.getByLabelText("Open comparison set: Second Set"));

    // set-2 resolves → detail is shown
    await waitFor(() => {
      expect(screen.getByTestId("lines-empty-state")).toBeInTheDocument();
    });

    // Now resolve set-1's stale response — it must NOT overwrite set-2's detail
    await act(async () => {
      resolveSet1!(makeFullSet("set-1", "First Set"));
    });

    // The heading in the detail panel should still be "Second Set", not "First Set"
    // (set-2 remains selected; stale set-1 response was discarded)
    // The "Second Set" title appears in the section header of the detail panel
    const sectionTitles = screen.getAllByText("Second Set");
    expect(sectionTitles.length).toBeGreaterThanOrEqual(1);

    // "First Set" must NOT appear in the detail panel header — confirm it only
    // appears in the list button, not as a section title
    const firstSetElements = screen.getAllByText("First Set");
    // They should only be the list item button labels, not a detail section heading
    firstSetElements.forEach((el) => {
      expect(el.closest("[data-testid='tender-comparison-summary-strip']")).toBeNull();
    });
  });

  it("stale response error does not surface as detail error banner", async () => {
    mockList.mockResolvedValue({
      total: 2,
      items: [
        makeSetItem("set-1", "First Set"),
        makeSetItem("set-2", "Second Set"),
      ],
    });

    // set-1 detail rejects slowly; set-2 resolves immediately
    let rejectSet1: (e: Error) => void;
    const set1Promise = new Promise<never>((_, reject) => {
      rejectSet1 = reject;
    });

    mockGetSet.mockImplementation((id: string) => {
      if (id === "set-1") return set1Promise;
      return Promise.resolve(makeFullSet("set-2", "Second Set"));
    });
    mockGetSummary.mockImplementation((id: string) => {
      if (id === "set-1") return set1Promise;
      return Promise.resolve(makeSummary("set-2"));
    });

    render(<TenderComparisonClient />);
    await waitFor(() =>
      expect(screen.getByText("First Set")).toBeInTheDocument(),
    );

    // Select set-1 (slow, will error), then immediately select set-2 (succeeds)
    fireEvent.click(screen.getByLabelText("Open comparison set: First Set"));
    fireEvent.click(screen.getByLabelText("Open comparison set: Second Set"));

    // set-2 resolves — detail shown with no error
    await waitFor(() => {
      expect(screen.getByTestId("lines-empty-state")).toBeInTheDocument();
    });

    // Now reject set-1's stale request — must NOT show an error banner
    await act(async () => {
      rejectSet1!(new Error("set-1 fetch failed"));
    });

    // No detail error banner should appear because this error is from a
    // superseded request
    expect(screen.queryByTestId("detail-error-state")).not.toBeInTheDocument();
  });

  // ── Baseline governance (PR-V6-13) ──────────────────────────────────────────

  it("shows Approve as Baseline button for non-approved set", async () => {
    mockList.mockResolvedValue({
      total: 1,
      items: [makeSetItem("set-1", "Q1 Comparison")],
    });
    mockGetSet.mockResolvedValue(
      makeFullSet("set-1", "Q1 Comparison", { is_approved_baseline: false }),
    );
    mockGetSummary.mockResolvedValue(makeSummary("set-1"));

    render(<TenderComparisonClient />);
    await waitFor(() =>
      expect(screen.getByText("Q1 Comparison")).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByLabelText("Open comparison set: Q1 Comparison"));
    await waitFor(() =>
      expect(screen.getByTestId("approve-baseline-button")).toBeInTheDocument(),
    );
  });

  it("does not show Approve as Baseline button when set is already approved", async () => {
    mockList.mockResolvedValue({
      total: 1,
      items: [makeSetItem("set-1", "Q1 Comparison", { is_approved_baseline: true })],
    });
    mockGetSet.mockResolvedValue(
      makeFullSet("set-1", "Q1 Comparison", {
        is_approved_baseline: true,
        approved_at: "2026-03-01T00:00:00Z",
        approved_by_user_id: "user-1",
      }),
    );
    mockGetSummary.mockResolvedValue(makeSummary("set-1"));

    render(<TenderComparisonClient />);
    await waitFor(() =>
      expect(screen.getByText("Q1 Comparison")).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByLabelText("Open comparison set: Q1 Comparison"));
    await waitFor(() =>
      expect(screen.getByTestId("detail-baseline-badge")).toBeInTheDocument(),
    );
    expect(screen.queryByTestId("approve-baseline-button")).not.toBeInTheDocument();
  });

  it("opens confirmation modal when Approve as Baseline is clicked", async () => {
    mockList.mockResolvedValue({
      total: 1,
      items: [makeSetItem("set-1", "Q1 Comparison")],
    });
    mockGetSet.mockResolvedValue(makeFullSet("set-1", "Q1 Comparison"));
    mockGetSummary.mockResolvedValue(makeSummary("set-1"));

    render(<TenderComparisonClient />);
    await waitFor(() =>
      expect(screen.getByText("Q1 Comparison")).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByLabelText("Open comparison set: Q1 Comparison"));
    await waitFor(() =>
      expect(screen.getByTestId("approve-baseline-button")).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByTestId("approve-baseline-button"));
    expect(screen.getByTestId("baseline-approval-modal")).toBeInTheDocument();
  });

  it("closes confirmation modal on cancel without calling API", async () => {
    mockList.mockResolvedValue({
      total: 1,
      items: [makeSetItem("set-1", "Q1 Comparison")],
    });
    mockGetSet.mockResolvedValue(makeFullSet("set-1", "Q1 Comparison"));
    mockGetSummary.mockResolvedValue(makeSummary("set-1"));

    render(<TenderComparisonClient />);
    await waitFor(() =>
      expect(screen.getByText("Q1 Comparison")).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByLabelText("Open comparison set: Q1 Comparison"));
    await waitFor(() =>
      expect(screen.getByTestId("approve-baseline-button")).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByTestId("approve-baseline-button"));
    expect(screen.getByTestId("baseline-approval-modal")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Cancel"));
    expect(screen.queryByTestId("baseline-approval-modal")).not.toBeInTheDocument();
    expect(mockApprove).not.toHaveBeenCalled();
  });

  it("calls approveTenderBaseline and refreshes on confirm", async () => {
    const approvedSet = makeFullSet("set-1", "Q1 Comparison", {
      is_approved_baseline: true,
      approved_at: "2026-03-28T00:00:00Z",
      approved_by_user_id: "test-user",
    });
    mockList.mockResolvedValue({
      total: 1,
      items: [makeSetItem("set-1", "Q1 Comparison")],
    });
    mockGetSet.mockResolvedValue(makeFullSet("set-1", "Q1 Comparison"));
    mockGetSummary.mockResolvedValue(makeSummary("set-1"));
    mockApprove.mockResolvedValue(approvedSet);

    render(<TenderComparisonClient />);
    await waitFor(() =>
      expect(screen.getByText("Q1 Comparison")).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByLabelText("Open comparison set: Q1 Comparison"));
    await waitFor(() =>
      expect(screen.getByTestId("approve-baseline-button")).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByTestId("approve-baseline-button"));
    fireEvent.click(screen.getByTestId("confirm-approve-baseline"));

    await waitFor(() => {
      expect(mockApprove).toHaveBeenCalledWith("set-1");
    });
  });

  it("shows Approved Baseline badge and metadata strip for approved set", async () => {
    mockList.mockResolvedValue({
      total: 1,
      items: [makeSetItem("set-1", "Q1 Comparison", { is_approved_baseline: true })],
    });
    mockGetSet.mockResolvedValue(
      makeFullSet("set-1", "Q1 Comparison", {
        is_approved_baseline: true,
        approved_at: "2026-03-28T10:00:00Z",
        approved_by_user_id: "user-42",
      }),
    );
    mockGetSummary.mockResolvedValue(makeSummary("set-1"));

    render(<TenderComparisonClient />);
    await waitFor(() =>
      expect(screen.getByText("Q1 Comparison")).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByLabelText("Open comparison set: Q1 Comparison"));
    await waitFor(() => {
      expect(screen.getByTestId("detail-baseline-badge")).toBeInTheDocument();
      expect(screen.getByTestId("baseline-meta-strip")).toBeInTheDocument();
    });
    expect(screen.getByText(/user-42/)).toBeInTheDocument();
  });
});
