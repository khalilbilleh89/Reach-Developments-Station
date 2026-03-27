/**
 * ScenariosPage tests
 *
 * Validates the Scenario Workspace frontend:
 *   - scenario list rendering
 *   - create scenario modal
 *   - duplication modal
 *   - lifecycle controls (approve/archive)
 *   - comparison selection and view
 */
import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";

// Mock Next.js navigation
let mockSearchParamsStr = "";
const mockRouterPush = jest.fn();
jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockRouterPush }),
  usePathname: () => "/scenarios",
  useSearchParams: () => new URLSearchParams(mockSearchParamsStr),
}));

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

// Mock CSS modules
jest.mock("@/styles/demo-shell.module.css", () => ({
  kpiGrid: "kpiGrid",
  tableWrapper: "tableWrapper",
  table: "table",
  badge: "badge",
  badgeGreen: "badgeGreen",
  badgeBlue: "badgeBlue",
  badgeGray: "badgeGray",
  badgePurple: "badgePurple",
  btnOutline: "btnOutline",
  monospaceCell: "monospaceCell",
  errorBanner: "errorBanner",
}));
jest.mock("@/components/shell/PageContainer.module.css", () => ({}));

// Mock MetricCard
jest.mock("@/components/dashboard/MetricCard", () => ({
  MetricCard: ({
    label,
    value,
  }: {
    label: string;
    value: string;
  }) => (
    <div data-testid="metric-card">
      <span>{label}</span>
      <span>{value}</span>
    </div>
  ),
}));

// Mock PageContainer
jest.mock("@/components/shell/PageContainer", () => ({
  PageContainer: ({
    children,
    title,
  }: {
    children: React.ReactNode;
    title?: string;
  }) => (
    <div>
      {title && <h1>{title}</h1>}
      {children}
    </div>
  ),
}));

// Mock scenario-api
jest.mock("@/lib/scenario-api", () => ({
  listScenarios: jest.fn(),
  getScenario: jest.fn(),
  createScenario: jest.fn(),
  duplicateScenario: jest.fn(),
  approveScenario: jest.fn(),
  archiveScenario: jest.fn(),
  compareScenarios: jest.fn(),
}));

import {
  listScenarios,
  getScenario,
  createScenario,
  duplicateScenario,
  approveScenario,
  archiveScenario,
  compareScenarios,
} from "@/lib/scenario-api";
import ScenariosPage from "@/app/(protected)/scenarios/page";

const mockListScenarios = listScenarios as jest.Mock;
const mockGetScenario = getScenario as jest.Mock;
const mockCreateScenario = createScenario as jest.Mock;
const mockDuplicateScenario = duplicateScenario as jest.Mock;
const mockApproveScenario = approveScenario as jest.Mock;
const mockArchiveScenario = archiveScenario as jest.Mock;
const mockCompareScenarios = compareScenarios as jest.Mock;

const mockScenario1 = {
  id: "sc-1",
  name: "Marina Tower — Base Case",
  code: "MT-BASE-01",
  status: "draft",
  source_type: "manual",
  project_id: null,
  land_id: null,
  base_scenario_id: null,
  is_active: true,
  notes: "Base case assumptions",
  created_at: "2025-01-15T10:00:00Z",
  updated_at: "2025-01-15T10:00:00Z",
};

const mockScenario2 = {
  id: "sc-2",
  name: "Marina Tower — Upside",
  code: "MT-UP-01",
  status: "approved",
  source_type: "manual",
  project_id: null,
  land_id: null,
  base_scenario_id: "sc-1",
  is_active: true,
  notes: null,
  created_at: "2025-01-16T10:00:00Z",
  updated_at: "2025-01-16T10:00:00Z",
};

const mockScenarioList = {
  items: [mockScenario1, mockScenario2],
  total: 2,
};

beforeEach(() => {
  jest.clearAllMocks();
  mockSearchParamsStr = "";
  mockListScenarios.mockResolvedValue(mockScenarioList);
});

// ---------------------------------------------------------------------------
// List view
// ---------------------------------------------------------------------------

describe("ScenariosPage — list view", () => {
  it("renders the page title", async () => {
    render(<ScenariosPage />);
    await waitFor(() => expect(mockListScenarios).toHaveBeenCalled());
    expect(screen.getByText("Scenarios")).toBeInTheDocument();
  });

  it("displays KPI cards with correct counts", async () => {
    render(<ScenariosPage />);
    await waitFor(() => expect(screen.getByText("Marina Tower — Base Case")).toBeInTheDocument());

    const cards = screen.getAllByTestId("metric-card");
    const cardTexts = cards.map((c) => c.textContent ?? "");
    expect(cardTexts.some((t) => t.includes("Total Scenarios") && t.includes("2"))).toBe(true);
    expect(cardTexts.some((t) => t.includes("Draft") && t.includes("1"))).toBe(true);
    expect(cardTexts.some((t) => t.includes("Approved") && t.includes("1"))).toBe(true);
  });

  it("renders scenario names in the table", async () => {
    render(<ScenariosPage />);
    await waitFor(() => {
      expect(screen.getByText("Marina Tower — Base Case")).toBeInTheDocument();
      expect(screen.getByText("Marina Tower — Upside")).toBeInTheDocument();
    });
  });

  it("renders scenario codes", async () => {
    render(<ScenariosPage />);
    await waitFor(() => {
      expect(screen.getByText("MT-BASE-01")).toBeInTheDocument();
      expect(screen.getByText("MT-UP-01")).toBeInTheDocument();
    });
  });

  it("renders status badges", async () => {
    render(<ScenariosPage />);
    await waitFor(() => {
      expect(screen.getAllByText("Draft").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("Approved").length).toBeGreaterThanOrEqual(1);
    });
  });

  it("shows empty state when no scenarios", async () => {
    mockListScenarios.mockResolvedValueOnce({ items: [], total: 0 });
    render(<ScenariosPage />);
    await waitFor(() => {
      expect(screen.getByText(/No scenarios found/)).toBeInTheDocument();
    });
  });

  it("shows error message on API failure", async () => {
    mockListScenarios.mockRejectedValueOnce(new Error("Network error"));
    render(<ScenariosPage />);
    await waitFor(() => {
      expect(screen.getByText("Network error")).toBeInTheDocument();
    });
  });

  it("shows New Scenario button", async () => {
    render(<ScenariosPage />);
    await waitFor(() => expect(mockListScenarios).toHaveBeenCalled());
    expect(screen.getByText("+ New Scenario")).toBeInTheDocument();
  });

  it("renders Duplicate and View action buttons for each scenario", async () => {
    render(<ScenariosPage />);
    await waitFor(() => {
      expect(screen.getByText("Marina Tower — Base Case")).toBeInTheDocument();
    });
    const duplicateButtons = screen.getAllByText("Duplicate");
    const viewButtons = screen.getAllByText("View");
    expect(duplicateButtons.length).toBeGreaterThanOrEqual(2);
    expect(viewButtons.length).toBeGreaterThanOrEqual(2);
  });

  it("applies status filter and reloads", async () => {
    render(<ScenariosPage />);
    await waitFor(() => expect(mockListScenarios).toHaveBeenCalledTimes(1));

    const select = screen.getByLabelText("Status:");
    fireEvent.change(select, { target: { value: "draft" } });

    await waitFor(() =>
      expect(mockListScenarios).toHaveBeenCalledWith(
        expect.objectContaining({ status: "draft" }),
      ),
    );
  });

  it("clears selection and compare button when filter changes", async () => {
    render(<ScenariosPage />);
    await waitFor(() => expect(screen.getByText("Marina Tower — Base Case")).toBeInTheDocument());

    // Select two rows
    const checkboxes = screen.getAllByRole("checkbox");
    fireEvent.click(checkboxes[0]);
    fireEvent.click(checkboxes[1]);
    expect(screen.getByText(/Compare \(2\)/)).toBeInTheDocument();

    // Change filter — loadScenarios re-runs, which clears selectedIds
    const select = screen.getByLabelText("Status:");
    fireEvent.change(select, { target: { value: "draft" } });

    await waitFor(() => expect(mockListScenarios).toHaveBeenCalledTimes(2));
    expect(screen.queryByText(/Compare \(/)).not.toBeInTheDocument();
  });

  it("clears selection after create refreshes the list", async () => {
    const newScenario = { ...mockScenario1, id: "sc-new", name: "New Test Scenario" };
    mockCreateScenario.mockResolvedValueOnce(newScenario);
    mockListScenarios.mockResolvedValue({
      items: [mockScenario1, mockScenario2, newScenario],
      total: 3,
    });

    render(<ScenariosPage />);
    await waitFor(() => expect(screen.getByText("Marina Tower — Base Case")).toBeInTheDocument());

    // Select rows before creating
    const checkboxes = screen.getAllByRole("checkbox");
    fireEvent.click(checkboxes[0]);
    fireEvent.click(checkboxes[1]);
    expect(screen.getByText(/Compare \(2\)/)).toBeInTheDocument();

    // Create a scenario (triggers refresh which clears selection)
    fireEvent.click(screen.getByText("+ New Scenario"));
    fireEvent.change(screen.getByLabelText(/Name \*/), { target: { value: "New Test Scenario" } });
    fireEvent.click(screen.getByText("Create Scenario"));

    await waitFor(() => expect(mockListScenarios).toHaveBeenCalledTimes(2));
    expect(screen.queryByText(/Compare \(/)).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Create scenario modal
// ---------------------------------------------------------------------------

describe("ScenariosPage — create scenario modal", () => {
  it("opens create modal when New Scenario is clicked", async () => {
    render(<ScenariosPage />);
    await waitFor(() => expect(mockListScenarios).toHaveBeenCalled());

    fireEvent.click(screen.getByText("+ New Scenario"));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("New Scenario")).toBeInTheDocument();
  });

  it("closes modal on Cancel", async () => {
    render(<ScenariosPage />);
    await waitFor(() => expect(mockListScenarios).toHaveBeenCalled());

    fireEvent.click(screen.getByText("+ New Scenario"));
    fireEvent.click(screen.getByText("Cancel"));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("shows validation error when name is empty", async () => {
    render(<ScenariosPage />);
    await waitFor(() => expect(mockListScenarios).toHaveBeenCalled());

    fireEvent.click(screen.getByText("+ New Scenario"));
    fireEvent.click(screen.getByText("Create Scenario"));

    await waitFor(() => {
      expect(screen.getByText("Scenario name is required.")).toBeInTheDocument();
    });
  });

  it("calls createScenario with correct payload and refreshes list", async () => {
    const newScenario = { ...mockScenario1, id: "sc-new", name: "New Test Scenario" };
    mockCreateScenario.mockResolvedValueOnce(newScenario);
    mockListScenarios.mockResolvedValue({ items: [newScenario], total: 1 });

    render(<ScenariosPage />);
    await waitFor(() => expect(mockListScenarios).toHaveBeenCalled());

    fireEvent.click(screen.getByText("+ New Scenario"));

    fireEvent.change(screen.getByLabelText(/Name \*/), {
      target: { value: "New Test Scenario" },
    });
    fireEvent.change(screen.getByLabelText("Code"), {
      target: { value: "NTS-01" },
    });

    fireEvent.click(screen.getByText("Create Scenario"));

    await waitFor(() => {
      expect(mockCreateScenario).toHaveBeenCalledWith(
        expect.objectContaining({ name: "New Test Scenario", code: "NTS-01" }),
      );
    });
    await waitFor(() => expect(mockListScenarios).toHaveBeenCalledTimes(2));
  });

  it("shows API error inside modal on create failure", async () => {
    mockCreateScenario.mockRejectedValueOnce(new Error("Create failed"));

    render(<ScenariosPage />);
    await waitFor(() => expect(mockListScenarios).toHaveBeenCalled());

    fireEvent.click(screen.getByText("+ New Scenario"));
    fireEvent.change(screen.getByLabelText(/Name \*/), {
      target: { value: "Error Scenario" },
    });
    fireEvent.click(screen.getByText("Create Scenario"));

    await waitFor(() => {
      expect(screen.getByText("Create failed")).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// Duplicate scenario modal
// ---------------------------------------------------------------------------

describe("ScenariosPage — duplicate scenario modal", () => {
  it("opens duplicate modal when Duplicate is clicked", async () => {
    render(<ScenariosPage />);
    await waitFor(() => expect(screen.getByText("Marina Tower — Base Case")).toBeInTheDocument());

    const duplicateButtons = screen.getAllByText("Duplicate");
    fireEvent.click(duplicateButtons[0]);

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText(/Duplicate:/)).toBeInTheDocument();
  });

  it("pre-fills duplicate name with (Copy) suffix", async () => {
    render(<ScenariosPage />);
    await waitFor(() => expect(screen.getByText("Marina Tower — Base Case")).toBeInTheDocument());

    fireEvent.click(screen.getAllByText("Duplicate")[0]);

    const nameInput = screen.getByLabelText(/New Name \*/);
    expect((nameInput as HTMLInputElement).value).toBe("Marina Tower — Base Case (Copy)");
  });

  it("calls duplicateScenario with correct data", async () => {
    const duplicated = { ...mockScenario1, id: "sc-dup", name: "Marina Tower — Dup" };
    mockDuplicateScenario.mockResolvedValueOnce(duplicated);
    mockListScenarios.mockResolvedValue({ items: [mockScenario1, duplicated], total: 2 });

    render(<ScenariosPage />);
    await waitFor(() => expect(screen.getByText("Marina Tower — Base Case")).toBeInTheDocument());

    fireEvent.click(screen.getAllByText("Duplicate")[0]);

    fireEvent.change(screen.getByLabelText(/New Name \*/), {
      target: { value: "Marina Tower — Dup" },
    });
    fireEvent.click(screen.getByText("Duplicate Scenario"));

    await waitFor(() => {
      expect(mockDuplicateScenario).toHaveBeenCalledWith(
        "sc-1",
        expect.objectContaining({ name: "Marina Tower — Dup" }),
      );
    });
    await waitFor(() => expect(mockListScenarios).toHaveBeenCalledTimes(2));
  });

  it("shows error on duplicate failure", async () => {
    mockDuplicateScenario.mockRejectedValueOnce(new Error("Duplicate failed"));

    render(<ScenariosPage />);
    await waitFor(() => expect(screen.getByText("Marina Tower — Base Case")).toBeInTheDocument());

    fireEvent.click(screen.getAllByText("Duplicate")[0]);
    fireEvent.click(screen.getByText("Duplicate Scenario"));

    await waitFor(() => {
      expect(screen.getByText("Duplicate failed")).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// Detail view
// ---------------------------------------------------------------------------

describe("ScenariosPage — detail view", () => {
  it("navigates to detail view when scenario name is clicked", async () => {
    render(<ScenariosPage />);
    await waitFor(() => expect(screen.getByText("Marina Tower — Base Case")).toBeInTheDocument());

    fireEvent.click(screen.getByText("Marina Tower — Base Case"));

    expect(screen.getByText("← Back to Scenarios")).toBeInTheDocument();
  });

  it("shows Approve button for draft scenario", async () => {
    render(<ScenariosPage />);
    await waitFor(() => expect(screen.getByText("Marina Tower — Base Case")).toBeInTheDocument());

    fireEvent.click(screen.getByText("Marina Tower — Base Case"));

    expect(screen.getByText("Approve")).toBeInTheDocument();
  });

  it("does not show Approve button for approved scenario", async () => {
    render(<ScenariosPage />);
    await waitFor(() => expect(screen.getByText("Marina Tower — Upside")).toBeInTheDocument());

    fireEvent.click(screen.getByText("Marina Tower — Upside"));

    expect(screen.queryByText("Approve")).not.toBeInTheDocument();
  });

  it("calls approveScenario and updates UI", async () => {
    const approved = { ...mockScenario1, status: "approved" as const };
    mockApproveScenario.mockResolvedValueOnce(approved);

    render(<ScenariosPage />);
    await waitFor(() => expect(screen.getByText("Marina Tower — Base Case")).toBeInTheDocument());

    fireEvent.click(screen.getByText("Marina Tower — Base Case"));
    fireEvent.click(screen.getByText("Approve"));

    await waitFor(() => {
      expect(mockApproveScenario).toHaveBeenCalledWith("sc-1");
    });
  });

  it("calls archiveScenario on Archive click", async () => {
    const archived = { ...mockScenario1, status: "archived" as const };
    mockArchiveScenario.mockResolvedValueOnce(archived);

    render(<ScenariosPage />);
    await waitFor(() => expect(screen.getByText("Marina Tower — Base Case")).toBeInTheDocument());

    fireEvent.click(screen.getByText("Marina Tower — Base Case"));
    fireEvent.click(screen.getByText("Archive"));

    await waitFor(() => {
      expect(mockArchiveScenario).toHaveBeenCalledWith("sc-1");
    });
  });

  it("shows lifecycle error on approve failure", async () => {
    mockApproveScenario.mockRejectedValueOnce(new Error("Approve failed"));

    render(<ScenariosPage />);
    await waitFor(() => expect(screen.getByText("Marina Tower — Base Case")).toBeInTheDocument());

    fireEvent.click(screen.getByText("Marina Tower — Base Case"));
    fireEvent.click(screen.getByText("Approve"));

    await waitFor(() => {
      expect(screen.getByText("Approve failed")).toBeInTheDocument();
    });
  });

  it("navigates back to list via back button", async () => {
    render(<ScenariosPage />);
    await waitFor(() => expect(screen.getByText("Marina Tower — Base Case")).toBeInTheDocument());

    fireEvent.click(screen.getByText("Marina Tower — Base Case"));
    fireEvent.click(screen.getByText("← Back to Scenarios"));

    expect(screen.getByText("+ New Scenario")).toBeInTheDocument();
  });

  it("shows notes in detail view", async () => {
    render(<ScenariosPage />);
    await waitFor(() => expect(screen.getByText("Marina Tower — Base Case")).toBeInTheDocument());

    fireEvent.click(screen.getByText("Marina Tower — Base Case"));

    expect(screen.getByText(/Base case assumptions/)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Comparison
// ---------------------------------------------------------------------------

describe("ScenariosPage — comparison", () => {
  it("shows Compare button when 2+ scenarios are selected", async () => {
    render(<ScenariosPage />);
    await waitFor(() => expect(screen.getByText("Marina Tower — Base Case")).toBeInTheDocument());

    const checkboxes = screen.getAllByRole("checkbox");
    fireEvent.click(checkboxes[0]);
    fireEvent.click(checkboxes[1]);

    expect(screen.getByText(/Compare \(2\)/)).toBeInTheDocument();
  });

  it("calls compareScenarios and opens comparison modal", async () => {
    const compareResult = {
      scenarios: [
        {
          scenario_id: "sc-1",
          scenario_name: "Marina Tower — Base Case",
          status: "draft",
          latest_version_number: 1,
          assumptions_json: { gdv: 1000000 },
          comparison_metrics_json: null,
        },
        {
          scenario_id: "sc-2",
          scenario_name: "Marina Tower — Upside",
          status: "approved",
          latest_version_number: 2,
          assumptions_json: null,
          comparison_metrics_json: null,
        },
      ],
    };
    mockCompareScenarios.mockResolvedValueOnce(compareResult);

    render(<ScenariosPage />);
    await waitFor(() => expect(screen.getByText("Marina Tower — Base Case")).toBeInTheDocument());

    const checkboxes = screen.getAllByRole("checkbox");
    fireEvent.click(checkboxes[0]);
    fireEvent.click(checkboxes[1]);
    fireEvent.click(screen.getByText(/Compare \(2\)/));

    await waitFor(() => {
      expect(mockCompareScenarios).toHaveBeenCalledWith({
        scenario_ids: expect.arrayContaining(["sc-1", "sc-2"]),
      });
    });

    await waitFor(() => {
      expect(screen.getByText("Scenario Comparison")).toBeInTheDocument();
    });

    expect(screen.getByLabelText("Scenario comparison")).toBeInTheDocument();
  });

  it("closes comparison modal via Close button", async () => {
    const compareResult = {
      scenarios: [
        {
          scenario_id: "sc-1",
          scenario_name: "Marina Tower — Base Case",
          status: "draft",
          latest_version_number: null,
          assumptions_json: null,
          comparison_metrics_json: null,
        },
        {
          scenario_id: "sc-2",
          scenario_name: "Marina Tower — Upside",
          status: "approved",
          latest_version_number: null,
          assumptions_json: null,
          comparison_metrics_json: null,
        },
      ],
    };
    mockCompareScenarios.mockResolvedValueOnce(compareResult);

    render(<ScenariosPage />);
    await waitFor(() => expect(screen.getByText("Marina Tower — Base Case")).toBeInTheDocument());

    const checkboxes = screen.getAllByRole("checkbox");
    fireEvent.click(checkboxes[0]);
    fireEvent.click(checkboxes[1]);
    fireEvent.click(screen.getByText(/Compare \(2\)/));

    await waitFor(() => {
      expect(screen.getByText("Scenario Comparison")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Close"));
    expect(screen.queryByText("Scenario Comparison")).not.toBeInTheDocument();
  });

  it("shows error when compare API fails", async () => {
    mockCompareScenarios.mockRejectedValueOnce(new Error("Compare failed"));

    render(<ScenariosPage />);
    await waitFor(() => expect(screen.getByText("Marina Tower — Base Case")).toBeInTheDocument());

    const checkboxes = screen.getAllByRole("checkbox");
    fireEvent.click(checkboxes[0]);
    fireEvent.click(checkboxes[1]);
    fireEvent.click(screen.getByText(/Compare \(2\)/));

    await waitFor(() => {
      expect(screen.getByText("Compare failed")).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// PR-V6-03 — Lifecycle linking tests
// ---------------------------------------------------------------------------

describe("ScenariosPage — land_id query param filter", () => {
  it("shows land filter banner when land_id param is present", async () => {
    mockSearchParamsStr = "land_id=land-abc-123";
    render(<ScenariosPage />);
    await waitFor(() => expect(mockListScenarios).toHaveBeenCalled());
    expect(screen.getByTestId("land-filter-banner")).toBeInTheDocument();
    expect(screen.getByText(/land-abc-123/)).toBeInTheDocument();
  });

  it("does not show land filter banner when no land_id param", async () => {
    render(<ScenariosPage />);
    await waitFor(() => expect(mockListScenarios).toHaveBeenCalled());
    expect(screen.queryByTestId("land-filter-banner")).not.toBeInTheDocument();
  });

  it("calls listScenarios with land_id filter when param is present", async () => {
    mockSearchParamsStr = "land_id=land-abc-123";
    render(<ScenariosPage />);
    await waitFor(() =>
      expect(mockListScenarios).toHaveBeenCalledWith(
        expect.objectContaining({ land_id: "land-abc-123" }),
      ),
    );
  });

  it("shows create scenario modal pre-opened when new=1 param is present", async () => {
    mockSearchParamsStr = "new=1";
    render(<ScenariosPage />);
    await waitFor(() => expect(mockListScenarios).toHaveBeenCalled());
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("shows land context in create modal when both land_id and new=1 are present", async () => {
    mockSearchParamsStr = "land_id=land-abc-123&new=1";
    render(<ScenariosPage />);
    await waitFor(() => expect(mockListScenarios).toHaveBeenCalled());
    expect(screen.getByTestId("create-scenario-land-context")).toBeInTheDocument();
  });

  it("includes land_id in createScenario call when modal opened from land context", async () => {
    mockSearchParamsStr = "land_id=land-xyz-999&new=1";
    const newScenario = { ...mockScenario1, id: "sc-new", land_id: "land-xyz-999" };
    mockCreateScenario.mockResolvedValueOnce(newScenario);
    mockListScenarios.mockResolvedValue({ items: [newScenario], total: 1 });

    render(<ScenariosPage />);
    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText(/Name \*/), {
      target: { value: "Linked Scenario" },
    });
    fireEvent.click(screen.getByText("Create Scenario"));

    await waitFor(() =>
      expect(mockCreateScenario).toHaveBeenCalledWith(
        expect.objectContaining({ land_id: "land-xyz-999" }),
      ),
    );
  });
});

describe("ScenariosPage — detail view lifecycle cross-links", () => {
  it("shows lifecycle cross-links panel in detail view", async () => {
    render(<ScenariosPage />);
    await waitFor(() =>
      expect(screen.getByText("Marina Tower — Base Case")).toBeInTheDocument(),
    );

    fireEvent.click(screen.getAllByText("View")[0]);
    await waitFor(() =>
      expect(screen.getByTestId("scenario-lifecycle-links")).toBeInTheDocument(),
    );
  });

  it("shows 'View Feasibility Runs' button in detail view", async () => {
    render(<ScenariosPage />);
    await waitFor(() =>
      expect(screen.getByText("Marina Tower — Base Case")).toBeInTheDocument(),
    );

    fireEvent.click(screen.getAllByText("View")[0]);
    await waitFor(() =>
      expect(
        screen.getByTestId("scenario-view-feasibility-btn"),
      ).toBeInTheDocument(),
    );
  });

  it("shows '+ Run Feasibility' button in detail view", async () => {
    render(<ScenariosPage />);
    await waitFor(() =>
      expect(screen.getByText("Marina Tower — Base Case")).toBeInTheDocument(),
    );

    fireEvent.click(screen.getAllByText("View")[0]);
    await waitFor(() =>
      expect(
        screen.getByTestId("scenario-run-feasibility-btn"),
      ).toBeInTheDocument(),
    );
  });

  it("navigates to feasibility filtered by scenario_id when View Feasibility Runs clicked", async () => {
    render(<ScenariosPage />);
    await waitFor(() =>
      expect(screen.getByText("Marina Tower — Base Case")).toBeInTheDocument(),
    );

    fireEvent.click(screen.getAllByText("View")[0]);
    await waitFor(() =>
      expect(screen.getByTestId("scenario-view-feasibility-btn")).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByTestId("scenario-view-feasibility-btn"));
    expect(mockRouterPush).toHaveBeenCalledWith(
      expect.stringContaining("/feasibility"),
    );
    expect(mockRouterPush).toHaveBeenCalledWith(
      expect.stringContaining("sc-1"),
    );
  });

  it("shows 'Open Land' button when scenario has a land_id", async () => {
    const scenarioWithLand = { ...mockScenario1, land_id: "land-abc-001" };
    mockListScenarios.mockResolvedValueOnce({
      items: [scenarioWithLand],
      total: 1,
    });

    render(<ScenariosPage />);
    await waitFor(() =>
      expect(screen.getByText("Marina Tower — Base Case")).toBeInTheDocument(),
    );

    fireEvent.click(screen.getAllByText("View")[0]);
    await waitFor(() =>
      expect(screen.getByTestId("scenario-open-land-btn")).toBeInTheDocument(),
    );
  });

  it("shows 'No linked land parcel' when scenario has no land_id", async () => {
    render(<ScenariosPage />);
    await waitFor(() =>
      expect(screen.getByText("Marina Tower — Base Case")).toBeInTheDocument(),
    );

    fireEvent.click(screen.getAllByText("View")[0]);
    await waitFor(() =>
      expect(screen.getByTestId("scenario-no-land-link")).toBeInTheDocument(),
    );
  });

  it("navigates to /land with parcel_id when Open Land button clicked", async () => {
    const scenarioWithLand = { ...mockScenario1, land_id: "land-abc-001" };
    mockListScenarios.mockResolvedValueOnce({
      items: [scenarioWithLand],
      total: 1,
    });

    render(<ScenariosPage />);
    await waitFor(() =>
      expect(screen.getByText("Marina Tower — Base Case")).toBeInTheDocument(),
    );

    fireEvent.click(screen.getAllByText("View")[0]);
    await waitFor(() =>
      expect(screen.getByTestId("scenario-open-land-btn")).toBeInTheDocument(),
    );

    fireEvent.click(screen.getByTestId("scenario-open-land-btn"));
    expect(mockRouterPush).toHaveBeenCalledWith(
      "/land?parcel_id=land-abc-001",
    );
  });
});

describe("ScenariosPage — scenario_id query param auto-opens detail", () => {
  it("auto-opens detail view when scenario_id param matches a loaded scenario", async () => {
    mockSearchParamsStr = "scenario_id=sc-1";
    render(<ScenariosPage />);
    await waitFor(() =>
      expect(screen.getByTestId("scenario-lifecycle-links")).toBeInTheDocument(),
    );
    // Detail view is open
    expect(screen.getByTestId("scenario-lifecycle-links")).toBeInTheDocument();
  });

  it("fetches scenario directly when scenario_id is not in the loaded list", async () => {
    const remoteScenario = {
      ...mockScenario1,
      id: "sc-remote",
      name: "Remote Scenario",
    };
    mockSearchParamsStr = "scenario_id=sc-remote";
    mockGetScenario.mockResolvedValue(remoteScenario);

    render(<ScenariosPage />);
    await waitFor(() =>
      expect(mockGetScenario).toHaveBeenCalledWith("sc-remote"),
    );
    await waitFor(() =>
      expect(screen.getByText("Remote Scenario")).toBeInTheDocument(),
    );
  });

  it("stays on list view when scenario_id fetch fails", async () => {
    mockSearchParamsStr = "scenario_id=sc-not-found";
    mockGetScenario.mockRejectedValue(new Error("Not found"));

    render(<ScenariosPage />);
    await waitFor(() => expect(mockListScenarios).toHaveBeenCalled());
    await waitFor(() => expect(mockGetScenario).toHaveBeenCalledWith("sc-not-found"));

    // Should stay on list view — no crash, no detail panel
    expect(
      screen.queryByTestId("scenario-lifecycle-links"),
    ).not.toBeInTheDocument();
    expect(
      screen.getByText("Marina Tower — Base Case"),
    ).toBeInTheDocument();
  });

  it("does not call getScenario when no scenario_id param", async () => {
    render(<ScenariosPage />);
    await waitFor(() => expect(mockListScenarios).toHaveBeenCalled());
    expect(mockGetScenario).not.toHaveBeenCalled();
  });
});
