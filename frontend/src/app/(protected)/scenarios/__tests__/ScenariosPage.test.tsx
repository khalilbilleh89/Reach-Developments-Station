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
jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: jest.fn() }),
  usePathname: () => "/scenarios",
  useSearchParams: () => new URLSearchParams(""),
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
  createScenario: jest.fn(),
  duplicateScenario: jest.fn(),
  approveScenario: jest.fn(),
  archiveScenario: jest.fn(),
  compareScenarios: jest.fn(),
}));

import {
  listScenarios,
  createScenario,
  duplicateScenario,
  approveScenario,
  archiveScenario,
  compareScenarios,
} from "@/lib/scenario-api";
import ScenariosPage from "@/app/(protected)/scenarios/page";

const mockListScenarios = listScenarios as jest.Mock;
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
