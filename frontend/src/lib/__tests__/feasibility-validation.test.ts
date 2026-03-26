/**
 * feasibility-validation.test.ts
 *
 * Unit tests for the feasibility assumptions client-side validation utility.
 * Covers happy path and every error-path edge case expected by the backend.
 */

import {
  validateFeasibilityAssumptions,
  parseFeasibilityAssumptionsPayload,
  AssumptionsFormInputs,
} from "@/lib/validation/feasibility-assumptions";

/** A baseline set of fully valid form inputs. */
const validInputs: AssumptionsFormInputs = {
  sellableArea: "5000",
  avgSalePrice: "3000",
  constructionCost: "800",
  softCostRatio: "10",
  financeCostRatio: "5",
  salesCostRatio: "3",
  devPeriod: "24",
};

// ---------------------------------------------------------------------------
// Happy path
// ---------------------------------------------------------------------------

describe("validateFeasibilityAssumptions — valid inputs", () => {
  test("returns valid: true and empty errors for all-valid inputs", () => {
    const result = validateFeasibilityAssumptions(validInputs);
    expect(result.valid).toBe(true);
    expect(result.errors).toEqual({});
  });

  test("accepts ratio value of exactly 0", () => {
    const result = validateFeasibilityAssumptions({
      ...validInputs,
      softCostRatio: "0",
      financeCostRatio: "0",
      salesCostRatio: "0",
    });
    expect(result.valid).toBe(true);
    expect(result.errors).toEqual({});
  });

  test("accepts ratio value of exactly 100", () => {
    const result = validateFeasibilityAssumptions({
      ...validInputs,
      softCostRatio: "100",
    });
    expect(result.valid).toBe(true);
    expect(result.errors.softCostRatio).toBeUndefined();
  });

  test("accepts development period of exactly 1", () => {
    const result = validateFeasibilityAssumptions({
      ...validInputs,
      devPeriod: "1",
    });
    expect(result.valid).toBe(true);
    expect(result.errors.devPeriod).toBeUndefined();
  });

  test("accepts fractional positive values for price/area/cost fields", () => {
    const result = validateFeasibilityAssumptions({
      ...validInputs,
      sellableArea: "0.5",
      avgSalePrice: "999.99",
      constructionCost: "0.01",
    });
    expect(result.valid).toBe(true);
    expect(result.errors).toEqual({});
  });
});

// ---------------------------------------------------------------------------
// sellableArea validation
// ---------------------------------------------------------------------------

describe("validateFeasibilityAssumptions — sellableArea", () => {
  test("rejects zero", () => {
    const result = validateFeasibilityAssumptions({
      ...validInputs,
      sellableArea: "0",
    });
    expect(result.valid).toBe(false);
    expect(result.errors.sellableArea).toMatch(/invalid value for sellable area/i);
  });

  test("rejects negative value", () => {
    const result = validateFeasibilityAssumptions({
      ...validInputs,
      sellableArea: "-1",
    });
    expect(result.valid).toBe(false);
    expect(result.errors.sellableArea).toMatch(/invalid value for sellable area/i);
  });

  test("rejects NaN (non-numeric string)", () => {
    const result = validateFeasibilityAssumptions({
      ...validInputs,
      sellableArea: "abc",
    });
    expect(result.valid).toBe(false);
    expect(result.errors.sellableArea).toMatch(/invalid value for sellable area/i);
  });

  test("rejects Infinity string", () => {
    const result = validateFeasibilityAssumptions({
      ...validInputs,
      sellableArea: "Infinity",
    });
    expect(result.valid).toBe(false);
    expect(result.errors.sellableArea).toMatch(/invalid value for sellable area/i);
  });
});

// ---------------------------------------------------------------------------
// avgSalePrice validation
// ---------------------------------------------------------------------------

describe("validateFeasibilityAssumptions — avgSalePrice", () => {
  test("rejects zero", () => {
    const result = validateFeasibilityAssumptions({
      ...validInputs,
      avgSalePrice: "0",
    });
    expect(result.valid).toBe(false);
    expect(result.errors.avgSalePrice).toMatch(/invalid value for avg sale price/i);
  });

  test("rejects negative value", () => {
    const result = validateFeasibilityAssumptions({
      ...validInputs,
      avgSalePrice: "-500",
    });
    expect(result.valid).toBe(false);
    expect(result.errors.avgSalePrice).toMatch(/invalid value for avg sale price/i);
  });

  test("rejects NaN", () => {
    const result = validateFeasibilityAssumptions({
      ...validInputs,
      avgSalePrice: "NaN",
    });
    expect(result.valid).toBe(false);
    expect(result.errors.avgSalePrice).toMatch(/invalid value for avg sale price/i);
  });

  test("rejects Infinity", () => {
    const result = validateFeasibilityAssumptions({
      ...validInputs,
      avgSalePrice: "Infinity",
    });
    expect(result.valid).toBe(false);
    expect(result.errors.avgSalePrice).toMatch(/invalid value for avg sale price/i);
  });
});

// ---------------------------------------------------------------------------
// constructionCost validation
// ---------------------------------------------------------------------------

describe("validateFeasibilityAssumptions — constructionCost", () => {
  test("rejects zero", () => {
    const result = validateFeasibilityAssumptions({
      ...validInputs,
      constructionCost: "0",
    });
    expect(result.valid).toBe(false);
    expect(result.errors.constructionCost).toMatch(
      /invalid value for construction cost/i,
    );
  });

  test("rejects negative value", () => {
    const result = validateFeasibilityAssumptions({
      ...validInputs,
      constructionCost: "-100",
    });
    expect(result.valid).toBe(false);
    expect(result.errors.constructionCost).toMatch(
      /invalid value for construction cost/i,
    );
  });

  test("rejects Infinity", () => {
    const result = validateFeasibilityAssumptions({
      ...validInputs,
      constructionCost: "Infinity",
    });
    expect(result.valid).toBe(false);
    expect(result.errors.constructionCost).toMatch(
      /invalid value for construction cost/i,
    );
  });
});

// ---------------------------------------------------------------------------
// Ratio fields: softCostRatio, financeCostRatio, salesCostRatio
// ---------------------------------------------------------------------------

describe("validateFeasibilityAssumptions — ratio fields", () => {
  test("rejects softCostRatio above 100", () => {
    const result = validateFeasibilityAssumptions({
      ...validInputs,
      softCostRatio: "101",
    });
    expect(result.valid).toBe(false);
    expect(result.errors.softCostRatio).toMatch(
      /soft cost ratio must be between 0 and 100/i,
    );
  });

  test("rejects softCostRatio below 0 (negative)", () => {
    const result = validateFeasibilityAssumptions({
      ...validInputs,
      softCostRatio: "-1",
    });
    expect(result.valid).toBe(false);
    expect(result.errors.softCostRatio).toMatch(
      /soft cost ratio must be between 0 and 100/i,
    );
  });

  test("rejects softCostRatio that is Infinity", () => {
    const result = validateFeasibilityAssumptions({
      ...validInputs,
      softCostRatio: "Infinity",
    });
    expect(result.valid).toBe(false);
    expect(result.errors.softCostRatio).toMatch(
      /soft cost ratio must be between 0 and 100/i,
    );
  });

  test("rejects financeCostRatio above 100", () => {
    const result = validateFeasibilityAssumptions({
      ...validInputs,
      financeCostRatio: "150",
    });
    expect(result.valid).toBe(false);
    expect(result.errors.financeCostRatio).toMatch(
      /finance cost ratio must be between 0 and 100/i,
    );
  });

  test("rejects financeCostRatio below 0", () => {
    const result = validateFeasibilityAssumptions({
      ...validInputs,
      financeCostRatio: "-5",
    });
    expect(result.valid).toBe(false);
    expect(result.errors.financeCostRatio).toMatch(
      /finance cost ratio must be between 0 and 100/i,
    );
  });

  test("rejects salesCostRatio above 100", () => {
    const result = validateFeasibilityAssumptions({
      ...validInputs,
      salesCostRatio: "200",
    });
    expect(result.valid).toBe(false);
    expect(result.errors.salesCostRatio).toMatch(
      /sales cost ratio must be between 0 and 100/i,
    );
  });

  test("rejects salesCostRatio below 0", () => {
    const result = validateFeasibilityAssumptions({
      ...validInputs,
      salesCostRatio: "-0.1",
    });
    expect(result.valid).toBe(false);
    expect(result.errors.salesCostRatio).toMatch(
      /sales cost ratio must be between 0 and 100/i,
    );
  });

  test("rejects NaN string for ratio field", () => {
    const result = validateFeasibilityAssumptions({
      ...validInputs,
      salesCostRatio: "abc",
    });
    expect(result.valid).toBe(false);
    expect(result.errors.salesCostRatio).toMatch(
      /sales cost ratio must be between 0 and 100/i,
    );
  });
});

// ---------------------------------------------------------------------------
// devPeriod validation
// ---------------------------------------------------------------------------

describe("validateFeasibilityAssumptions — devPeriod", () => {
  test("rejects decimal (12.9 is not an integer)", () => {
    const result = validateFeasibilityAssumptions({
      ...validInputs,
      devPeriod: "12.9",
    });
    expect(result.valid).toBe(false);
    expect(result.errors.devPeriod).toMatch(/whole number of months/i);
  });

  test("rejects zero", () => {
    const result = validateFeasibilityAssumptions({
      ...validInputs,
      devPeriod: "0",
    });
    expect(result.valid).toBe(false);
    expect(result.errors.devPeriod).toMatch(/whole number of months/i);
  });

  test("rejects negative integer", () => {
    const result = validateFeasibilityAssumptions({
      ...validInputs,
      devPeriod: "-12",
    });
    expect(result.valid).toBe(false);
    expect(result.errors.devPeriod).toMatch(/whole number of months/i);
  });

  test("rejects NaN string", () => {
    const result = validateFeasibilityAssumptions({
      ...validInputs,
      devPeriod: "abc",
    });
    expect(result.valid).toBe(false);
    expect(result.errors.devPeriod).toMatch(/whole number of months/i);
  });

  test("rejects Infinity", () => {
    const result = validateFeasibilityAssumptions({
      ...validInputs,
      devPeriod: "Infinity",
    });
    expect(result.valid).toBe(false);
    expect(result.errors.devPeriod).toMatch(/whole number of months/i);
  });
});

// ---------------------------------------------------------------------------
// Multiple simultaneous errors
// ---------------------------------------------------------------------------

describe("validateFeasibilityAssumptions — multiple errors", () => {
  test("collects errors for multiple invalid fields simultaneously", () => {
    const result = validateFeasibilityAssumptions({
      sellableArea: "-1",
      avgSalePrice: "0",
      constructionCost: "abc",
      softCostRatio: "150",
      financeCostRatio: "-5",
      salesCostRatio: "200",
      devPeriod: "12.5",
    });
    expect(result.valid).toBe(false);
    expect(result.errors.sellableArea).toBeDefined();
    expect(result.errors.avgSalePrice).toBeDefined();
    expect(result.errors.constructionCost).toBeDefined();
    expect(result.errors.softCostRatio).toBeDefined();
    expect(result.errors.financeCostRatio).toBeDefined();
    expect(result.errors.salesCostRatio).toBeDefined();
    expect(result.errors.devPeriod).toBeDefined();
  });
});

// ---------------------------------------------------------------------------
// parseFeasibilityAssumptionsPayload
// ---------------------------------------------------------------------------

describe("parseFeasibilityAssumptionsPayload", () => {
  test("converts ratio percent inputs to decimal values for backend", () => {
    const payload = parseFeasibilityAssumptionsPayload(validInputs);
    expect(payload.sellable_area_sqm).toBe(5000);
    expect(payload.avg_sale_price_per_sqm).toBe(3000);
    expect(payload.construction_cost_per_sqm).toBe(800);
    expect(payload.soft_cost_ratio).toBeCloseTo(0.1);
    expect(payload.finance_cost_ratio).toBeCloseTo(0.05);
    expect(payload.sales_cost_ratio).toBeCloseTo(0.03);
    expect(payload.development_period_months).toBe(24);
  });

  test("converts 0 percent ratio to 0 decimal", () => {
    const payload = parseFeasibilityAssumptionsPayload({
      ...validInputs,
      softCostRatio: "0",
    });
    expect(payload.soft_cost_ratio).toBe(0);
  });

  test("converts 100 percent ratio to 1 decimal", () => {
    const payload = parseFeasibilityAssumptionsPayload({
      ...validInputs,
      salesCostRatio: "100",
    });
    expect(payload.sales_cost_ratio).toBe(1);
  });
});
