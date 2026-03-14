/**
 * SalesReadinessCard tests
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";

jest.mock("@/styles/sales-workflow.module.css", () => ({}));

import { SalesReadinessCard } from "@/components/sales/SalesReadinessCard";
import type { UnitListItem, UnitPrice } from "@/lib/units-types";

const mockUnit: UnitListItem = {
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

const mockPricing: UnitPrice = {
  unit_id: "unit-1",
  unit_area: 85,
  base_unit_price: 900_000,
  premium_total: 50_000,
  final_unit_price: 950_000,
};

describe("SalesReadinessCard", () => {
  it("shows 'Ready' badge for available, priced unit", () => {
    render(
      <SalesReadinessCard
        unit={mockUnit}
        pricing={mockPricing}
        hasApprovedException={false}
        contractStatus={null}
        readiness="ready"
      />,
    );
    expect(screen.getByText("Ready")).toBeInTheDocument();
  });

  it("shows 'Missing Pricing' badge when pricing is null", () => {
    render(
      <SalesReadinessCard
        unit={mockUnit}
        pricing={null}
        hasApprovedException={false}
        contractStatus={null}
        readiness="missing_pricing"
      />,
    );
    expect(screen.getByText("Missing Pricing")).toBeInTheDocument();
  });

  it("shows 'Under Contract' badge when under_contract", () => {
    render(
      <SalesReadinessCard
        unit={{ ...mockUnit, status: "under_contract" }}
        pricing={mockPricing}
        hasApprovedException={false}
        contractStatus="active"
        readiness="under_contract"
      />,
    );
    expect(screen.getByText("Under Contract")).toBeInTheDocument();
  });

  it("shows pricing available check passing", () => {
    render(
      <SalesReadinessCard
        unit={mockUnit}
        pricing={mockPricing}
        hasApprovedException={false}
        contractStatus={null}
        readiness="ready"
      />,
    );
    expect(screen.getByText("Pricing is available")).toBeInTheDocument();
  });

  it("shows approved exception check when hasApprovedException is true", () => {
    render(
      <SalesReadinessCard
        unit={mockUnit}
        pricing={mockPricing}
        hasApprovedException={true}
        contractStatus={null}
        readiness="ready"
      />,
    );
    expect(screen.getByText("Approved exception on file")).toBeInTheDocument();
  });

  it("does not show approved exception check when none", () => {
    render(
      <SalesReadinessCard
        unit={mockUnit}
        pricing={mockPricing}
        hasApprovedException={false}
        contractStatus={null}
        readiness="ready"
      />,
    );
    expect(
      screen.queryByText("Approved exception on file"),
    ).not.toBeInTheDocument();
  });

  it("shows 'Blocked' readiness badge", () => {
    render(
      <SalesReadinessCard
        unit={{ ...mockUnit, status: "registered" }}
        pricing={mockPricing}
        hasApprovedException={false}
        contractStatus={null}
        readiness="blocked"
      />,
    );
    expect(screen.getByText("Blocked")).toBeInTheDocument();
  });

  it("shows 'Needs Exception Approval' badge when hasPendingException is true", () => {
    render(
      <SalesReadinessCard
        unit={mockUnit}
        pricing={mockPricing}
        hasApprovedException={false}
        hasPendingException={true}
        contractStatus={null}
        readiness="needs_exception_approval"
      />,
    );
    expect(screen.getByText("Needs Exception Approval")).toBeInTheDocument();
    expect(
      screen.getByText("Pending exception awaiting approval"),
    ).toBeInTheDocument();
  });

  it("does not show pending exception check when hasPendingException is false", () => {
    render(
      <SalesReadinessCard
        unit={mockUnit}
        pricing={mockPricing}
        hasApprovedException={false}
        hasPendingException={false}
        contractStatus={null}
        readiness="ready"
      />,
    );
    expect(
      screen.queryByText("Pending exception awaiting approval"),
    ).not.toBeInTheDocument();
  });
});
