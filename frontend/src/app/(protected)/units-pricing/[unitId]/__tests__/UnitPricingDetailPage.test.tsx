/**
 * UnitPricingDetailView tests
 */
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";

// Mock Next.js navigation — useSearchParams provides ?unitId=unit-1
let mockSearchParams = new URLSearchParams("unitId=unit-1");
jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: jest.fn() }),
  usePathname: () => "/units-pricing",
  useSearchParams: () => mockSearchParams,
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
  getUnitPricingDetail: jest.fn(),
}));

import { getUnitPricingDetail } from "@/lib/units-api";
import UnitPricingDetailView from "@/components/units/UnitPricingDetailView";

const mockGetUnitPricingDetail = getUnitPricingDetail as jest.Mock;

const mockUnit = {
  id: "unit-1",
  floor_id: "floor-1",
  unit_number: "A101",
  unit_type: "two_bedroom",
  status: "available",
  internal_area: 85.5,
  balcony_area: 10,
  terrace_area: null,
  roof_garden_area: null,
  front_garden_area: null,
  gross_area: null,
};

const mockPricing = {
  unit_id: "unit-1",
  unit_area: 85.5,
  base_unit_price: 900_000,
  premium_total: 50_000,
  final_unit_price: 950_000,
};

const mockAttributes = {
  id: "attr-1",
  unit_id: "unit-1",
  base_price_per_sqm: 10_526,
  floor_premium: 20_000,
  view_premium: 30_000,
  corner_premium: 0,
  size_adjustment: 0,
  custom_adjustment: 0,
};

describe("UnitPricingDetailView", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockSearchParams = new URLSearchParams("unitId=unit-1");
  });

  it("renders loading state initially", () => {
    mockGetUnitPricingDetail.mockReturnValue(new Promise(() => {}));
    render(<UnitPricingDetailView />);
    expect(screen.getByText(/loading unit details/i)).toBeInTheDocument();
  });

  it("renders unit title after load", async () => {
    mockGetUnitPricingDetail.mockResolvedValue({
      unit: mockUnit,
      pricing: mockPricing,
      attributes: mockAttributes,
      pricingState: "READY",
      readiness: null,
    });
    render(<UnitPricingDetailView />);
    await waitFor(() =>
      expect(screen.getByText("Unit A101")).toBeInTheDocument(),
    );
  });

  it("renders final price", async () => {
    mockGetUnitPricingDetail.mockResolvedValue({
      unit: mockUnit,
      pricing: mockPricing,
      attributes: mockAttributes,
      pricingState: "READY",
      readiness: null,
    });
    render(<UnitPricingDetailView />);
    await waitFor(() =>
      expect(screen.getAllByText(/950,000/).length).toBeGreaterThanOrEqual(1),
    );
  });

  it("renders unit attributes", async () => {
    mockGetUnitPricingDetail.mockResolvedValue({
      unit: mockUnit,
      pricing: mockPricing,
      attributes: mockAttributes,
      pricingState: "READY",
      readiness: null,
    });
    render(<UnitPricingDetailView />);
    await waitFor(() =>
      expect(screen.getAllByText("A101").length).toBeGreaterThanOrEqual(1),
    );
    expect(screen.getAllByText(/85\.5 sqm/).length).toBeGreaterThanOrEqual(1);
  });

  it("shows setup state when pricing attributes are missing (HTTP 422)", async () => {
    mockGetUnitPricingDetail.mockResolvedValue({
      unit: mockUnit,
      pricing: null,
      attributes: null,
      pricingState: "MISSING_ATTRIBUTES",
      readiness: null,
    });
    render(<UnitPricingDetailView />);
    await waitFor(() =>
      expect(
        screen.getByText(/Pricing Not Available Yet/i),
      ).toBeInTheDocument(),
    );
    expect(
      screen.getByText(/Required pricing attributes are missing/i),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Edit Attributes/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Edit Engine Inputs/i })).toBeInTheDocument();
  });

  it("shows specific missing fields when readiness provides them", async () => {
    mockGetUnitPricingDetail.mockResolvedValue({
      unit: mockUnit,
      pricing: null,
      attributes: null,
      pricingState: "MISSING_ATTRIBUTES",
      readiness: {
        unit_id: "unit-1",
        is_ready_for_pricing: false,
        missing_required_fields: ["base_price_per_sqm", "floor_premium"],
        readiness_reason: "The following required pricing engine fields are not set: base_price_per_sqm, floor_premium.",
      },
    });
    render(<UnitPricingDetailView />);
    await waitFor(() =>
      expect(screen.getByText(/Pricing Not Available Yet/i)).toBeInTheDocument(),
    );
    expect(screen.getAllByText(/base price per sqm/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/floor premium/i).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByRole("link", { name: /Edit Attributes/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Edit Engine Inputs/i })).toBeInTheDocument();
  });

  it("shows setup state when pricing record is missing", async () => {
    mockGetUnitPricingDetail.mockResolvedValue({
      unit: mockUnit,
      pricing: null,
      attributes: null,
      pricingState: "MISSING_PRICING_RECORD",
      readiness: null,
    });
    render(<UnitPricingDetailView />);
    await waitFor(() =>
      expect(
        screen.getByText(/Unit Pricing Not Configured/i),
      ).toBeInTheDocument(),
    );
    expect(
      screen.getByRole("link", { name: /Create Pricing Record/i }),
    ).toBeInTheDocument();
  });

  it("renders error state when fetch fails", async () => {
    mockGetUnitPricingDetail.mockRejectedValue(new Error("Unit not found"));
    render(<UnitPricingDetailView />);
    await waitFor(() =>
      expect(screen.getByText("Unit not found")).toBeInTheDocument(),
    );
  });

  it("renders back link", async () => {
    mockGetUnitPricingDetail.mockResolvedValue({
      unit: mockUnit,
      pricing: mockPricing,
      attributes: mockAttributes,
      pricingState: "READY",
      readiness: null,
    });
    render(<UnitPricingDetailView />);
    expect(
      screen.getByRole("link", { name: /back to units/i }),
    ).toBeInTheDocument();
  });

  it("renders pricing breakdown sections", async () => {
    mockGetUnitPricingDetail.mockResolvedValue({
      unit: mockUnit,
      pricing: mockPricing,
      attributes: mockAttributes,
      pricingState: "READY",
      readiness: null,
    });
    render(<UnitPricingDetailView />);
    await waitFor(() =>
      expect(screen.getByText("Pricing Breakdown")).toBeInTheDocument(),
    );
    expect(screen.getByText("Final Selling Price")).toBeInTheDocument();
    expect(screen.getByText("Base Unit Price")).toBeInTheDocument();
  });
});
