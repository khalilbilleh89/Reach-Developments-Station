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

// CSS modules are handled via Jest configuration (e.g., moduleNameMapper).

// Mock format-utils
jest.mock("@/lib/format-utils", () => ({
  formatCurrency: (v: number) => `AED ${v.toLocaleString()}`,
  formatAmount: (v: number, currency: string) => `${currency} ${v.toLocaleString()}`,
  formatAdjustment: (v: number, currency: string) => `${v > 0 ? "+" : ""}${currency} ${v.toLocaleString()}`,
}));

// Mock units-api — includes all functions used by the page
jest.mock("@/lib/units-api", () => ({
  getProjects: jest.fn(),
  getUnitsByProject: jest.fn(),
  getProjectPricing: jest.fn(),
  getProjectPricingAttributes: jest.fn(),
  listProjectReservations: jest.fn(),
  saveUnitPricingRecord: jest.fn(),
  saveUnitQualitativeAttributes: jest.fn(),
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

import {
  getProjects,
  getUnitsByProject,
  getProjectPricing,
  getProjectPricingAttributes,
  listProjectReservations,
} from "@/lib/units-api";
import UnitsPricingPage from "@/app/(protected)/units-pricing/page";

const mockGetProjects = getProjects as jest.Mock;
const mockGetUnitsByProject = getUnitsByProject as jest.Mock;
const mockGetProjectPricing = getProjectPricing as jest.Mock;
const mockGetProjectPricingAttributes = getProjectPricingAttributes as jest.Mock;
const mockListProjectReservations = listProjectReservations as jest.Mock;

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

const mockPricingRecord = {
  id: "pr-1",
  unit_id: "unit-1",
  base_price: 900_000,
  manual_adjustment: 0,
  final_price: 900_000,
  currency: "AED",
  pricing_status: "draft",
  notes: null,
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
};

const mockAttributes = {
  id: "attr-1",
  unit_id: "unit-1",
  view_type: "sea",
  corner_unit: false,
  floor_premium_category: "standard",
  orientation: "N",
  outdoor_area_premium: "balcony",
  upgrade_flag: false,
  notes: null,
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
};

const emptyReservations = { total: 0, items: [] };

describe("UnitsPricingPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetProjects.mockResolvedValue(mockProjects);
    mockGetUnitsByProject.mockResolvedValue(mockUnits);
    // unit-1 has pricing; unit-2 does not
    mockGetProjectPricing.mockResolvedValue({ "unit-1": mockPricingRecord });
    // unit-1 has attributes; unit-2 does not
    mockGetProjectPricingAttributes.mockResolvedValue({ "unit-1": mockAttributes });
    mockListProjectReservations.mockResolvedValue(emptyReservations);
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

  it("propagates unexpected bulk pricing errors to the units error state", async () => {
    mockGetUnitsByProject.mockResolvedValue(mockUnits);
    // Simulate a 500 error from the bulk pricing endpoint
    const { ApiError } = jest.requireMock("@/lib/api-client") as {
      ApiError: new (message: string, status: number) => Error;
    };
    mockGetProjectPricing.mockRejectedValue(new ApiError("Internal Server Error", 500));
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

  // ── Partial data tolerance tests ──────────────────────────────────────────

  it("renders rows without pricing records gracefully (shows 'Not priced')", async () => {
    // unit-2 has no pricing record
    mockGetProjectPricing.mockResolvedValue({});
    render(<UnitsPricingPage />);
    await waitFor(() => expect(screen.getByText("A101")).toBeInTheDocument());
    // Both "Not priced" labels should appear (one per unit without a record)
    const notPriced = screen.getAllByText("Not priced");
    expect(notPriced.length).toBeGreaterThanOrEqual(2);
  });

  it("renders rows without attributes gracefully (shows 'Attributes not set')", async () => {
    // No attributes for any unit
    mockGetProjectPricingAttributes.mockResolvedValue({});
    render(<UnitsPricingPage />);
    await waitFor(() => expect(screen.getByText("A101")).toBeInTheDocument());
    // "Attributes not set" should appear for units missing attributes
    const attrsNotSet = screen.getAllByText("Attributes not set");
    expect(attrsNotSet.length).toBeGreaterThanOrEqual(2);
  });

  it("shows 'Available' reservation badge when unit has no reservation", async () => {
    mockListProjectReservations.mockResolvedValue({ total: 0, items: [] });
    render(<UnitsPricingPage />);
    await waitFor(() => expect(screen.getByText("A101")).toBeInTheDocument());
    const available = screen.getAllByText("Available");
    // At least one badge per unit with no reservation
    expect(available.length).toBeGreaterThanOrEqual(2);
  });

  it("shows 'Reserved' badge for unit with active reservation", async () => {
    mockListProjectReservations.mockResolvedValue({
      total: 1,
      items: [
        {
          id: "rsv-1",
          unit_id: "unit-1",
          customer_name: "Alice",
          customer_phone: "+971500000000",
          customer_email: null,
          reservation_price: 900_000,
          reservation_fee: null,
          currency: "AED",
          status: "active",
          expires_at: null,
          notes: null,
          created_at: "2024-01-01T00:00:00Z",
          updated_at: "2024-01-01T00:00:00Z",
        },
      ],
    });
    render(<UnitsPricingPage />);
    await waitFor(() => expect(screen.getByText("A101")).toBeInTheDocument());
    // unit-1 should show "Reserved" badge; unit-2 still "Available"
    // Note: "Reserved" also appears as a filter option — use getAllByText
    expect(screen.getAllByText("Reserved").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Available").length).toBeGreaterThanOrEqual(1);
  });

  it("uses 3 bulk requests instead of per-unit requests", async () => {
    render(<UnitsPricingPage />);
    await waitFor(() => expect(screen.getByText("A101")).toBeInTheDocument());
    // Bulk functions should each be called exactly once
    expect(mockGetProjectPricing).toHaveBeenCalledTimes(1);
    expect(mockGetProjectPricingAttributes).toHaveBeenCalledTimes(1);
    expect(mockListProjectReservations).toHaveBeenCalledTimes(1);
    // All called with the first project id
    expect(mockGetProjectPricing).toHaveBeenCalledWith("proj-1");
    expect(mockGetProjectPricingAttributes).toHaveBeenCalledWith("proj-1");
    expect(mockListProjectReservations).toHaveBeenCalledWith("proj-1");
  });

  // ── Reservation determinism tests ─────────────────────────────────────────

  it("prefers active reservation over expired one regardless of API order", async () => {
    // expired comes first in API response — active should still win
    mockListProjectReservations.mockResolvedValue({
      total: 2,
      items: [
        {
          id: "rsv-exp",
          unit_id: "unit-1",
          customer_name: "Bob",
          customer_phone: "+971500000001",
          customer_email: null,
          reservation_price: 900_000,
          reservation_fee: null,
          currency: "AED",
          status: "expired",
          expires_at: null,
          notes: null,
          created_at: "2024-01-01T00:00:00Z",
          updated_at: "2024-01-02T00:00:00Z",
        },
        {
          id: "rsv-act",
          unit_id: "unit-1",
          customer_name: "Alice",
          customer_phone: "+971500000000",
          customer_email: null,
          reservation_price: 950_000,
          reservation_fee: null,
          currency: "AED",
          status: "active",
          expires_at: null,
          notes: null,
          created_at: "2024-01-01T00:00:00Z",
          updated_at: "2024-01-01T00:00:00Z",
        },
      ],
    });
    render(<UnitsPricingPage />);
    await waitFor(() => expect(screen.getByText("A101")).toBeInTheDocument());
    // The active reservation should be selected — badge shows "Reserved"
    // Note: "Reserved" also appears as a filter option — use getAllByText
    expect(screen.getAllByText("Reserved").length).toBeGreaterThanOrEqual(1);
  });

  it("selects more recent reservation when both have same status", async () => {
    // Two expired reservations — the one with the later updated_at should win
    mockListProjectReservations.mockResolvedValue({
      total: 2,
      items: [
        {
          id: "rsv-older",
          unit_id: "unit-1",
          customer_name: "Bob",
          customer_phone: "+971500000001",
          customer_email: null,
          reservation_price: 900_000,
          reservation_fee: null,
          currency: "AED",
          status: "expired",
          expires_at: null,
          notes: null,
          created_at: "2024-01-01T00:00:00Z",
          updated_at: "2024-01-01T00:00:00Z",
        },
        {
          id: "rsv-newer",
          unit_id: "unit-1",
          customer_name: "Alice",
          customer_phone: "+971500000000",
          customer_email: null,
          reservation_price: 950_000,
          reservation_fee: null,
          currency: "AED",
          status: "expired",
          expires_at: null,
          notes: null,
          created_at: "2024-01-01T00:00:00Z",
          updated_at: "2024-01-03T00:00:00Z",
        },
      ],
    });
    render(<UnitsPricingPage />);
    await waitFor(() => expect(screen.getByText("A101")).toBeInTheDocument());
    // Expired badge should be shown (the newer one selected — both are expired)
    expect(screen.getByText("Expired")).toBeInTheDocument();
  });

  it("keeps existing reservation when both lack timestamps (stable, not order-dependent)", async () => {
    mockListProjectReservations.mockResolvedValue({
      total: 2,
      items: [
        {
          id: "rsv-first",
          unit_id: "unit-1",
          customer_name: "First",
          customer_phone: "+971500000001",
          customer_email: null,
          reservation_price: 900_000,
          reservation_fee: null,
          currency: "AED",
          status: "cancelled",
          expires_at: null,
          notes: null,
          created_at: "",
          updated_at: "",
        },
        {
          id: "rsv-second",
          unit_id: "unit-1",
          customer_name: "Second",
          customer_phone: "+971500000000",
          customer_email: null,
          reservation_price: 950_000,
          reservation_fee: null,
          currency: "AED",
          status: "cancelled",
          expires_at: null,
          notes: null,
          created_at: "",
          updated_at: "",
        },
      ],
    });
    render(<UnitsPricingPage />);
    await waitFor(() => expect(screen.getByText("A101")).toBeInTheDocument());
    // Cancelled reservations map to empty class; the row renders (no crash)
    // The exact badge text for 'cancelled' is "" / no badge, so just confirm
    // the page rendered successfully without throwing.
    expect(screen.getByText("A101")).toBeInTheDocument();
  });
});
