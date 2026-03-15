/**
 * UnitsPricingPage tests
 */
import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";

// Mock Next.js navigation
jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: jest.fn() }),
  usePathname: () => "/units-pricing",
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
jest.mock("@/styles/units-pricing.module.css", () => ({}));
jest.mock("@/components/shell/PageContainer.module.css", () => ({}));

// Mock format-utils
jest.mock("@/lib/format-utils", () => ({
  formatCurrency: (v: number) => `AED ${v.toLocaleString()}`,
}));

// Mock units-api
jest.mock("@/lib/units-api", () => ({
  getProjects: jest.fn(),
  getUnitsByProject: jest.fn(),
  getUnitPricing: jest.fn(),
}));

// Import ApiError for constructing error fixtures
jest.mock("@/lib/api-client", () => ({
  apiFetch: jest.fn(),
  ApiError: class ApiError extends Error {
    constructor(message: string, public readonly status: number) {
      super(message);
      this.name = "ApiError";
    }
  },
}));

import { getProjects, getUnitsByProject, getUnitPricing } from "@/lib/units-api";
import UnitsPricingPage from "@/app/(protected)/units-pricing/page";

const mockGetProjects = getProjects as jest.Mock;
const mockGetUnitsByProject = getUnitsByProject as jest.Mock;
const mockGetUnitPricing = getUnitPricing as jest.Mock;

const mockProjects = [
  { id: "proj-1", name: "Marina Tower", code: "MT-01", status: "active" },
  { id: "proj-2", name: "Palm Villa", code: "PV-01", status: "active" },
];

const mockUnits = [
  {
    id: "unit-1",
    floor_id: "floor-1",
    unit_number: "A101",
    unit_type: "one_bedroom",
    status: "available",
    internal_area: 85.5,
    balcony_area: 10,
    terrace_area: null,
    roof_garden_area: null,
    front_garden_area: null,
    gross_area: null,
  },
  {
    id: "unit-2",
    floor_id: "floor-1",
    unit_number: "A102",
    unit_type: "two_bedroom",
    status: "under_contract",
    internal_area: 90.0,
    balcony_area: null,
    terrace_area: null,
    roof_garden_area: null,
    front_garden_area: null,
    gross_area: null,
  },
];

const mockPricing = {
  unit_id: "unit-1",
  unit_area: 85.5,
  base_unit_price: 900_000,
  premium_total: 50_000,
  final_unit_price: 950_000,
};

describe("UnitsPricingPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetProjects.mockResolvedValue(mockProjects);
    mockGetUnitsByProject.mockResolvedValue(mockUnits);
    mockGetUnitPricing.mockImplementation((id: string) =>
      id === "unit-1" ? Promise.resolve(mockPricing) : Promise.resolve(null),
    );
  });

  it("renders the page title", () => {
    render(<UnitsPricingPage />);
    expect(screen.getByText("Units & Pricing")).toBeInTheDocument();
  });

  it("loads and displays projects in selector", async () => {
    render(<UnitsPricingPage />);
    await waitFor(() =>
      expect(screen.getByRole("combobox", { name: /select project/i })).toBeInTheDocument(),
    );
    expect(screen.getByText("Marina Tower")).toBeInTheDocument();
    expect(screen.getByText("Palm Villa")).toBeInTheDocument();
  });

  it("loads and displays units after project is selected", async () => {
    render(<UnitsPricingPage />);
    await waitFor(() =>
      expect(screen.getByText("A101")).toBeInTheDocument(),
    );
    expect(screen.getByText("A102")).toBeInTheDocument();
  });

  it("shows unit count", async () => {
    render(<UnitsPricingPage />);
    await waitFor(() =>
      expect(screen.getByText(/2 units shown/i)).toBeInTheDocument(),
    );
  });

  it("switches project when selector changes", async () => {
    render(<UnitsPricingPage />);
    await waitFor(() =>
      expect(screen.getByRole("combobox", { name: /select project/i })).toBeInTheDocument(),
    );
    fireEvent.change(screen.getByRole("combobox", { name: /select project/i }), {
      target: { value: "proj-2" },
    });
    await waitFor(() => {
      expect(mockGetUnitsByProject).toHaveBeenCalledWith("proj-2");
    });
  });

  it("shows error state when units fetch fails", async () => {
    mockGetUnitsByProject.mockRejectedValue(new Error("Network error"));
    render(<UnitsPricingPage />);
    await waitFor(() =>
      expect(screen.getByText("Network error")).toBeInTheDocument(),
    );
  });

  it("propagates unexpected pricing errors to the units error state", async () => {
    mockGetUnitsByProject.mockResolvedValue(mockUnits);
    // Simulate a 500 error from pricing — not a 404 "not found"
    const { ApiError } = jest.requireMock("@/lib/api-client") as {
      ApiError: new (message: string, status: number) => Error;
    };
    mockGetUnitPricing.mockRejectedValue(new ApiError("Internal Server Error", 500));
    render(<UnitsPricingPage />);
    await waitFor(() =>
      expect(screen.getByText("Internal Server Error")).toBeInTheDocument(),
    );
  });

  it("shows empty state when no project is available", async () => {
    mockGetProjects.mockResolvedValue([]);
    render(<UnitsPricingPage />);
    await waitFor(() =>
      expect(screen.getByText(/no project selected/i)).toBeInTheDocument(),
    );
  });

  it("shows project error when projects fail to load", async () => {
    mockGetProjects.mockRejectedValue(new Error("Server error"));
    render(<UnitsPricingPage />);
    await waitFor(() =>
      expect(screen.getByText("Server error")).toBeInTheDocument(),
    );
  });

  it("applies status filter to shown units", async () => {
    render(<UnitsPricingPage />);
    // Wait for both units to load
    await waitFor(() =>
      expect(screen.getByText("A101")).toBeInTheDocument(),
    );
    // Change status filter to "available" — only A101 matches
    fireEvent.change(screen.getByLabelText(/status/i), {
      target: { value: "available" },
    });
    await waitFor(() =>
      expect(screen.getByText(/1 unit shown/i)).toBeInTheDocument(),
    );
    expect(screen.getByText("A101")).toBeInTheDocument();
    expect(screen.queryByText("A102")).not.toBeInTheDocument();
  });
});
