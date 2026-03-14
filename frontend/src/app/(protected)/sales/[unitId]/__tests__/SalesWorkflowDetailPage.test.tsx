/**
 * SalesWorkflowDetailPage tests
 */
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";

// Mock Next.js navigation
jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: jest.fn() }),
  usePathname: () => "/sales/unit-1",
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
  getUnitSaleWorkflow: jest.fn(),
}));

import { getUnitSaleWorkflow } from "@/lib/sales-api";
import SalesWorkflowDetailPage from "@/app/(protected)/sales/[unitId]/page";

const mockGetUnitSaleWorkflow = getUnitSaleWorkflow as jest.Mock;

const mockUnit = {
  id: "unit-1",
  floor_id: "floor-1",
  unit_number: "A101",
  unit_type: "one_bedroom",
  status: "available",
  internal_area: 85,
  balcony_area: 10,
  terrace_area: null,
  roof_garden_area: null,
  front_garden_area: null,
  gross_area: null,
};

const mockPricing = {
  unit_id: "unit-1",
  unit_area: 85,
  base_unit_price: 900_000,
  premium_total: 50_000,
  final_unit_price: 950_000,
};

const mockApprovedException = {
  id: "exc-1",
  exception_type: "discount",
  approval_status: "approved",
  base_price: 1_000_000,
  requested_price: 950_000,
  discount_amount: 50_000,
  discount_percentage: 5,
  incentive_value: null,
  incentive_description: null,
  requested_by: "Agent A",
  approved_by: "Manager B",
};

const mockContractAction = {
  kind: "available" as const,
  contractId: null,
  contractNumber: null,
  contractStatus: null,
};

const mockPaymentPlan = {
  contractId: "contract-1",
  totalInstallments: 12,
  totalDue: 950_000,
  nextDueDate: "2026-04-01",
  nextDueAmount: 79_166,
};

describe("SalesWorkflowDetailPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders loading state initially", () => {
    mockGetUnitSaleWorkflow.mockReturnValue(new Promise(() => {}));
    render(<SalesWorkflowDetailPage params={{ unitId: "unit-1" }} />);
    expect(screen.getByText(/loading sales workflow/i)).toBeInTheDocument();
  });

  it("renders unit number after load", async () => {
    mockGetUnitSaleWorkflow.mockResolvedValue({
      unit: mockUnit,
      pricing: mockPricing,
      approvedExceptions: [],
      contractAction: mockContractAction,
      paymentPlanPreview: null,
      readiness: "ready",
    });
    render(<SalesWorkflowDetailPage params={{ unitId: "unit-1" }} />);
    await waitFor(() =>
      expect(screen.getAllByText("A101").length).toBeGreaterThanOrEqual(1),
    );
  });

  it("renders final price", async () => {
    mockGetUnitSaleWorkflow.mockResolvedValue({
      unit: mockUnit,
      pricing: mockPricing,
      approvedExceptions: [],
      contractAction: mockContractAction,
      paymentPlanPreview: null,
      readiness: "ready",
    });
    render(<SalesWorkflowDetailPage params={{ unitId: "unit-1" }} />);
    await waitFor(() =>
      expect(screen.getAllByText(/950,000/).length).toBeGreaterThanOrEqual(1),
    );
  });

  it("renders back link", () => {
    mockGetUnitSaleWorkflow.mockReturnValue(new Promise(() => {}));
    render(<SalesWorkflowDetailPage params={{ unitId: "unit-1" }} />);
    expect(
      screen.getByRole("link", { name: /back to sales/i }),
    ).toBeInTheDocument();
  });

  it("renders approved exception when present", async () => {
    mockGetUnitSaleWorkflow.mockResolvedValue({
      unit: mockUnit,
      pricing: mockPricing,
      approvedExceptions: [mockApprovedException],
      contractAction: mockContractAction,
      paymentPlanPreview: null,
      readiness: "ready",
    });
    render(<SalesWorkflowDetailPage params={{ unitId: "unit-1" }} />);
    await waitFor(() =>
      expect(screen.getByText("Approved Exceptions")).toBeInTheDocument(),
    );
    expect(screen.getAllByText("Discount").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Approved")).toBeInTheDocument();
  });

  it("renders empty exception panel when no exceptions", async () => {
    mockGetUnitSaleWorkflow.mockResolvedValue({
      unit: mockUnit,
      pricing: mockPricing,
      approvedExceptions: [],
      contractAction: mockContractAction,
      paymentPlanPreview: null,
      readiness: "ready",
    });
    render(<SalesWorkflowDetailPage params={{ unitId: "unit-1" }} />);
    await waitFor(() =>
      expect(
        screen.getByText("No approved exceptions for this unit."),
      ).toBeInTheDocument(),
    );
  });

  it("renders contract action — available", async () => {
    mockGetUnitSaleWorkflow.mockResolvedValue({
      unit: mockUnit,
      pricing: mockPricing,
      approvedExceptions: [],
      contractAction: mockContractAction,
      paymentPlanPreview: null,
      readiness: "ready",
    });
    render(<SalesWorkflowDetailPage params={{ unitId: "unit-1" }} />);
    await waitFor(() =>
      expect(
        screen.getByText("Contract creation available"),
      ).toBeInTheDocument(),
    );
  });

  it("renders contract action — already active", async () => {
    mockGetUnitSaleWorkflow.mockResolvedValue({
      unit: mockUnit,
      pricing: mockPricing,
      approvedExceptions: [],
      contractAction: {
        kind: "already_active",
        contractId: "c-001",
        contractNumber: "CNT-001",
        contractStatus: "active",
      },
      paymentPlanPreview: null,
      readiness: "under_contract",
    });
    render(<SalesWorkflowDetailPage params={{ unitId: "unit-1" }} />);
    await waitFor(() =>
      expect(screen.getByText("Active contract exists")).toBeInTheDocument(),
    );
    expect(screen.getByText("CNT-001")).toBeInTheDocument();
  });

  it("renders payment plan preview when available", async () => {
    mockGetUnitSaleWorkflow.mockResolvedValue({
      unit: mockUnit,
      pricing: mockPricing,
      approvedExceptions: [],
      contractAction: mockContractAction,
      paymentPlanPreview: mockPaymentPlan,
      readiness: "ready",
    });
    render(<SalesWorkflowDetailPage params={{ unitId: "unit-1" }} />);
    await waitFor(() =>
      expect(screen.getByText("Payment Plan Preview")).toBeInTheDocument(),
    );
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText("2026-04-01")).toBeInTheDocument();
  });

  it("handles missing optional data gracefully (null pricing)", async () => {
    mockGetUnitSaleWorkflow.mockResolvedValue({
      unit: mockUnit,
      pricing: null,
      approvedExceptions: [],
      contractAction: { kind: "unavailable", contractId: null, contractNumber: null, contractStatus: null },
      paymentPlanPreview: null,
      readiness: "missing_pricing",
    });
    render(<SalesWorkflowDetailPage params={{ unitId: "unit-1" }} />);
    await waitFor(() =>
      expect(screen.getByText("Not priced")).toBeInTheDocument(),
    );
  });

  it("renders error state when fetch fails", async () => {
    mockGetUnitSaleWorkflow.mockRejectedValue(
      new Error("Failed to load sales workflow."),
    );
    render(<SalesWorkflowDetailPage params={{ unitId: "unit-1" }} />);
    await waitFor(() =>
      expect(
        screen.getByText("Failed to load sales workflow."),
      ).toBeInTheDocument(),
    );
  });
});
