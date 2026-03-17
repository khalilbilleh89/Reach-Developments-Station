/**
 * SalesWorkflowDetailView tests
 */
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";

// Mock Next.js navigation — useSearchParams provides ?unitId=unit-1&projectId=proj-1
let mockSearchParams = new URLSearchParams("unitId=unit-1&projectId=proj-1");
jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: jest.fn() }),
  usePathname: () => "/sales",
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
jest.mock("@/styles/sales-workflow.module.css", () => ({}));
jest.mock("@/components/shell/PageContainer.module.css", () => ({}));

// Mock format-utils
jest.mock("@/lib/format-utils", () => ({
  formatCurrency: (v: number) => `AED ${v.toLocaleString()}`,
  formatAmount: (v: number, currency: string) => `${currency} ${v.toLocaleString()}`,
}));

// Mock sales-api
jest.mock("@/lib/sales-api", () => ({
  getUnitSaleWorkflow: jest.fn(),
}));

import { getUnitSaleWorkflow } from "@/lib/sales-api";
import SalesWorkflowDetailView from "@/components/sales/SalesWorkflowDetailView";

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
  bedrooms: null,
  bathrooms: null,
  floor_level: null,
  livable_area: null,
  has_roof_garden: null,
};

const mockPricing = {
  unit_id: "unit-1",
  unit_area: 85,
  base_unit_price: 900_000,
  premium_total: 50_000,
  final_unit_price: 950_000,
  currency: "AED",
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

/** Base mock workflow detail with all required fields. */
const baseWorkflowDetail = {
  unit: mockUnit,
  pricing: mockPricing,
  approvedExceptions: [],
  contractAction: mockContractAction,
  paymentPlanPreview: null,
  readiness: "ready" as const,
  hasPendingException: false,
};

describe("SalesWorkflowDetailView", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockSearchParams = new URLSearchParams("unitId=unit-1&projectId=proj-1");
  });

  it("renders loading state initially", () => {
    mockGetUnitSaleWorkflow.mockReturnValue(new Promise(() => {}));
    render(<SalesWorkflowDetailView />);
    expect(screen.getByText(/loading sales workflow/i)).toBeInTheDocument();
  });

  it("calls getUnitSaleWorkflow with projectId from search params", async () => {
    mockSearchParams = new URLSearchParams("unitId=unit-1&projectId=proj-abc");
    mockGetUnitSaleWorkflow.mockResolvedValue(baseWorkflowDetail);
    render(<SalesWorkflowDetailView />);
    await waitFor(() =>
      expect(mockGetUnitSaleWorkflow).toHaveBeenCalledWith("proj-abc", "unit-1"),
    );
  });

  it("calls getUnitSaleWorkflow with empty string when projectId is absent", async () => {
    mockSearchParams = new URLSearchParams("unitId=unit-1");
    mockGetUnitSaleWorkflow.mockResolvedValue(baseWorkflowDetail);
    render(<SalesWorkflowDetailView />);
    await waitFor(() =>
      expect(mockGetUnitSaleWorkflow).toHaveBeenCalledWith("", "unit-1"),
    );
  });

  it("shows warning when projectId is missing", () => {
    mockSearchParams = new URLSearchParams("unitId=unit-1");
    mockGetUnitSaleWorkflow.mockReturnValue(new Promise(() => {}));
    render(<SalesWorkflowDetailView />);
    expect(
      screen.getByText(/no project context available/i),
    ).toBeInTheDocument();
  });

  it("does not show warning when projectId is present", () => {
    mockGetUnitSaleWorkflow.mockReturnValue(new Promise(() => {}));
    render(<SalesWorkflowDetailView />);
    expect(
      screen.queryByText(/no project context available/i),
    ).not.toBeInTheDocument();
  });

  it("renders unit number after load", async () => {
    mockGetUnitSaleWorkflow.mockResolvedValue(baseWorkflowDetail);
    render(<SalesWorkflowDetailView />);
    await waitFor(() =>
      expect(screen.getAllByText("A101").length).toBeGreaterThanOrEqual(1),
    );
  });

  it("renders final price", async () => {
    mockGetUnitSaleWorkflow.mockResolvedValue(baseWorkflowDetail);
    render(<SalesWorkflowDetailView />);
    await waitFor(() =>
      expect(screen.getAllByText(/950,000/).length).toBeGreaterThanOrEqual(1),
    );
  });

  it("renders back link", () => {
    mockGetUnitSaleWorkflow.mockReturnValue(new Promise(() => {}));
    render(<SalesWorkflowDetailView />);
    expect(
      screen.getByRole("link", { name: /back to sales/i }),
    ).toBeInTheDocument();
  });

  it("renders approved exception when present", async () => {
    mockGetUnitSaleWorkflow.mockResolvedValue({
      ...baseWorkflowDetail,
      approvedExceptions: [mockApprovedException],
    });
    render(<SalesWorkflowDetailView />);
    await waitFor(() =>
      expect(screen.getByText("Approved Exceptions")).toBeInTheDocument(),
    );
    expect(screen.getAllByText("Discount").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Approved")).toBeInTheDocument();
  });

  it("renders empty exception panel when no exceptions", async () => {
    mockGetUnitSaleWorkflow.mockResolvedValue(baseWorkflowDetail);
    render(<SalesWorkflowDetailView />);
    await waitFor(() =>
      expect(
        screen.getByText("No approved exceptions for this unit."),
      ).toBeInTheDocument(),
    );
  });

  it("renders needs_exception_approval readiness and pending check", async () => {
    mockGetUnitSaleWorkflow.mockResolvedValue({
      ...baseWorkflowDetail,
      readiness: "needs_exception_approval",
      hasPendingException: true,
    });
    render(<SalesWorkflowDetailView />);
    await waitFor(() =>
      expect(screen.getByText("Needs Exception Approval")).toBeInTheDocument(),
    );
    expect(
      screen.getByText("Pending exception awaiting approval"),
    ).toBeInTheDocument();
  });

  it("renders contract action — available", async () => {
    mockGetUnitSaleWorkflow.mockResolvedValue(baseWorkflowDetail);
    render(<SalesWorkflowDetailView />);
    await waitFor(() =>
      expect(
        screen.getByText("Contract creation available"),
      ).toBeInTheDocument(),
    );
  });

  it("renders contract action — already active", async () => {
    mockGetUnitSaleWorkflow.mockResolvedValue({
      ...baseWorkflowDetail,
      contractAction: {
        kind: "already_active",
        contractId: "c-001",
        contractNumber: "CNT-001",
        contractStatus: "active",
      },
      readiness: "under_contract",
    });
    render(<SalesWorkflowDetailView />);
    await waitFor(() =>
      expect(screen.getByText("Active contract exists")).toBeInTheDocument(),
    );
    expect(screen.getByText("CNT-001")).toBeInTheDocument();
  });

  it("renders payment plan preview when available", async () => {
    mockGetUnitSaleWorkflow.mockResolvedValue({
      ...baseWorkflowDetail,
      paymentPlanPreview: mockPaymentPlan,
    });
    render(<SalesWorkflowDetailView />);
    await waitFor(() =>
      expect(screen.getByText("Payment Plan Preview")).toBeInTheDocument(),
    );
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText("2026-04-01")).toBeInTheDocument();
  });

  it("handles missing optional data gracefully (null pricing)", async () => {
    mockGetUnitSaleWorkflow.mockResolvedValue({
      ...baseWorkflowDetail,
      pricing: null,
      contractAction: { kind: "unavailable", contractId: null, contractNumber: null, contractStatus: null },
      readiness: "missing_pricing",
    });
    render(<SalesWorkflowDetailView />);
    await waitFor(() =>
      expect(screen.getByText("Not priced")).toBeInTheDocument(),
    );
  });

  it("renders error state when fetch fails", async () => {
    mockGetUnitSaleWorkflow.mockRejectedValue(
      new Error("Failed to load sales workflow."),
    );
    render(<SalesWorkflowDetailView />);
    await waitFor(() =>
      expect(
        screen.getByText("Failed to load sales workflow."),
      ).toBeInTheDocument(),
    );
  });
});
