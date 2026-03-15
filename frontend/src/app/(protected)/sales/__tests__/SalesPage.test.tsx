/**
 * SalesPage tests
 */
import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";

// Mock Next.js navigation
const mockPush = jest.fn();
jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
  usePathname: () => "/sales",
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
jest.mock("@/styles/sales-workflow.module.css", () => ({}));
jest.mock("@/components/shell/PageContainer.module.css", () => ({}));

// Mock format-utils
jest.mock("@/lib/format-utils", () => ({
  formatCurrency: (v: number) => `AED ${v.toLocaleString()}`,
}));

// Mock sales-api
jest.mock("@/lib/sales-api", () => ({
  getProjects: jest.fn(),
  getSalesCandidates: jest.fn(),
  filterSalesCandidates: jest.fn((candidates: unknown[]) => candidates),
}));

import { getProjects, getSalesCandidates, filterSalesCandidates } from "@/lib/sales-api";
import SalesPage from "@/app/(protected)/sales/page";

const mockGetProjects = getProjects as jest.Mock;
const mockGetSalesCandidates = getSalesCandidates as jest.Mock;
const mockFilterSalesCandidates = filterSalesCandidates as jest.Mock;

const mockProjects = [
  { id: "proj-1", name: "Marina Tower", code: "MT-01", status: "active" },
  { id: "proj-2", name: "Palm Villa", code: "PV-01", status: "active" },
];

const mockUnit = {
  id: "unit-1",
  floor_id: "floor-1",
  unit_number: "A101",
  unit_type: "one_bedroom",
  status: "available",
  internal_area: 85,
  balcony_area: null,
  terrace_area: null,
  roof_garden_area: null,
  front_garden_area: null,
  gross_area: null,
};

const mockCandidates = [
  {
    unit: mockUnit,
    pricing: {
      unit_id: "unit-1",
      unit_area: 85,
      base_unit_price: 900_000,
      premium_total: 50_000,
      final_unit_price: 950_000,
    },
    hasApprovedException: false,
    contractStatus: null,
    readiness: "ready",
  },
];

describe("SalesPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockPush.mockReset();
    mockGetProjects.mockResolvedValue(mockProjects);
    mockGetSalesCandidates.mockResolvedValue(mockCandidates);
    mockFilterSalesCandidates.mockImplementation((c: unknown[]) => c);
  });

  it("renders the page title", () => {
    render(<SalesPage />);
    expect(screen.getByText("Sales")).toBeInTheDocument();
  });

  it("loads and displays projects in selector", async () => {
    render(<SalesPage />);
    await waitFor(() =>
      expect(
        screen.getByRole("combobox", { name: /select project/i }),
      ).toBeInTheDocument(),
    );
    expect(screen.getByText("Marina Tower")).toBeInTheDocument();
    expect(screen.getByText("Palm Villa")).toBeInTheDocument();
  });

  it("loads and displays sales candidates after project selected", async () => {
    render(<SalesPage />);
    await waitFor(() =>
      expect(screen.getByText("A101")).toBeInTheDocument(),
    );
  });

  it("shows unit count", async () => {
    render(<SalesPage />);
    await waitFor(() =>
      expect(screen.getByText(/1 unit shown/i)).toBeInTheDocument(),
    );
  });

  it("switches project when selector changes", async () => {
    render(<SalesPage />);
    await waitFor(() =>
      expect(
        screen.getByRole("combobox", { name: /select project/i }),
      ).toBeInTheDocument(),
    );
    fireEvent.change(
      screen.getByRole("combobox", { name: /select project/i }),
      { target: { value: "proj-2" } },
    );
    await waitFor(() => {
      expect(mockGetSalesCandidates).toHaveBeenCalledWith("proj-2");
    });
  });

  it("shows error state when candidates fetch fails", async () => {
    mockGetSalesCandidates.mockRejectedValue(new Error("Network error"));
    render(<SalesPage />);
    await waitFor(() =>
      expect(screen.getByText("Network error")).toBeInTheDocument(),
    );
  });

  it("shows empty state when no project is available", async () => {
    mockGetProjects.mockResolvedValue([]);
    render(<SalesPage />);
    await waitFor(() =>
      expect(screen.getByText(/no project selected/i)).toBeInTheDocument(),
    );
  });

  it("shows project error when projects fail to load", async () => {
    mockGetProjects.mockRejectedValue(new Error("Server error"));
    render(<SalesPage />);
    await waitFor(() =>
      expect(screen.getByText("Server error")).toBeInTheDocument(),
    );
  });

  it("navigates to unit detail with projectId query param", async () => {
    render(<SalesPage />);
    await waitFor(() =>
      expect(screen.getByText("A101")).toBeInTheDocument(),
    );
    fireEvent.click(
      screen.getByRole("button", { name: /open sales workflow/i }),
    );
    expect(mockPush).toHaveBeenCalledWith(
      expect.stringMatching(/\/sales\?unitId=unit-1&projectId=proj-1/),
    );
  });
});
