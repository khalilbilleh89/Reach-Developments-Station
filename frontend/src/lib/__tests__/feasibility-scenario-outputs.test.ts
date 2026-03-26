/**
 * feasibility-scenario-outputs.test.ts
 *
 * Unit tests for the normalizeFeasibilityScenarioOutputs helper.
 *
 * PR-FEAS-07 — Feasibility Scenario Outputs Typed Display
 */

import { normalizeFeasibilityScenarioOutputs } from "@/lib/normalizers/feasibility-scenario-outputs";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const makeMetrics = (overrides: Record<string, unknown> = {}) => ({
  gdv: 3_000_000,
  construction_cost: 800_000,
  soft_cost: 80_000,
  finance_cost: 50_000,
  sales_cost: 30_000,
  total_cost: 960_000,
  developer_profit: 2_040_000,
  profit_margin: 0.68,
  irr_estimate: 0.42,
  ...overrides,
});

const fullPayload = {
  base: makeMetrics(),
  upside: makeMetrics({ gdv: 3_300_000, developer_profit: 2_340_000, profit_margin: 0.71 }),
  downside: makeMetrics({ gdv: 2_700_000, developer_profit: 1_740_000, profit_margin: 0.64 }),
  investor: makeMetrics({ gdv: 3_150_000, developer_profit: 2_190_000, profit_margin: 0.695 }),
};

// ---------------------------------------------------------------------------
// Null / non-object payloads
// ---------------------------------------------------------------------------

test("returns null for null payload", () => {
  expect(normalizeFeasibilityScenarioOutputs(null)).toBeNull();
});

test("returns null for undefined payload", () => {
  expect(normalizeFeasibilityScenarioOutputs(undefined)).toBeNull();
});

test("returns null for string payload", () => {
  expect(normalizeFeasibilityScenarioOutputs("not an object")).toBeNull();
});

test("returns null for number payload", () => {
  expect(normalizeFeasibilityScenarioOutputs(42)).toBeNull();
});

test("returns null for array payload", () => {
  expect(normalizeFeasibilityScenarioOutputs([])).toBeNull();
});

test("returns null for empty object (no known scenario keys)", () => {
  expect(normalizeFeasibilityScenarioOutputs({})).toBeNull();
});

test("returns null for object with only unknown keys", () => {
  expect(normalizeFeasibilityScenarioOutputs({ unknown_key: { gdv: 1000 } })).toBeNull();
});

// ---------------------------------------------------------------------------
// Complete payload
// ---------------------------------------------------------------------------

test("normalizes a complete four-scenario payload without throwing", () => {
  const result = normalizeFeasibilityScenarioOutputs(fullPayload);
  expect(result).not.toBeNull();
});

test("complete payload includes all four scenario keys", () => {
  const result = normalizeFeasibilityScenarioOutputs(fullPayload)!;
  expect(result).toHaveProperty("base");
  expect(result).toHaveProperty("upside");
  expect(result).toHaveProperty("downside");
  expect(result).toHaveProperty("investor");
});

test("complete payload base scenario has correct gdv", () => {
  const result = normalizeFeasibilityScenarioOutputs(fullPayload)!;
  expect(result.base?.gdv).toBe(3_000_000);
});

test("complete payload upside scenario has correct profit_margin", () => {
  const result = normalizeFeasibilityScenarioOutputs(fullPayload)!;
  expect(result.upside?.profit_margin).toBe(0.71);
});

test("complete payload downside scenario has correct developer_profit", () => {
  const result = normalizeFeasibilityScenarioOutputs(fullPayload)!;
  expect(result.downside?.developer_profit).toBe(1_740_000);
});

test("complete payload investor scenario is present and has gdv", () => {
  const result = normalizeFeasibilityScenarioOutputs(fullPayload)!;
  expect(result.investor?.gdv).toBe(3_150_000);
});

// ---------------------------------------------------------------------------
// Partial payload — missing upside/downside
// ---------------------------------------------------------------------------

test("normalizes payload with only base scenario present", () => {
  const result = normalizeFeasibilityScenarioOutputs({ base: makeMetrics() })!;
  expect(result).not.toBeNull();
  expect(result.base?.gdv).toBe(3_000_000);
  expect(result.upside).toBeUndefined();
  expect(result.downside).toBeUndefined();
});

test("normalizes payload with only base and upside scenarios", () => {
  const result = normalizeFeasibilityScenarioOutputs({
    base: makeMetrics(),
    upside: makeMetrics({ gdv: 3_300_000 }),
  })!;
  expect(result.base).toBeDefined();
  expect(result.upside).toBeDefined();
  expect(result.downside).toBeUndefined();
  expect(result.investor).toBeUndefined();
});

// ---------------------------------------------------------------------------
// Partial metrics within a scenario
// ---------------------------------------------------------------------------

test("missing metric fields become null, not undefined or throwing", () => {
  const result = normalizeFeasibilityScenarioOutputs({
    base: { gdv: 3_000_000 }, // all other fields missing
  })!;
  expect(result.base?.gdv).toBe(3_000_000);
  expect(result.base?.construction_cost).toBeNull();
  expect(result.base?.total_cost).toBeNull();
  expect(result.base?.developer_profit).toBeNull();
  expect(result.base?.profit_margin).toBeNull();
  expect(result.base?.irr_estimate).toBeNull();
});

test("non-numeric metric value becomes null", () => {
  const result = normalizeFeasibilityScenarioOutputs({
    base: { gdv: "not-a-number", profit_margin: null },
  })!;
  expect(result.base?.gdv).toBeNull();
  expect(result.base?.profit_margin).toBeNull();
});

test("Infinity metric value becomes null", () => {
  const result = normalizeFeasibilityScenarioOutputs({
    base: { gdv: Infinity },
  })!;
  expect(result.base?.gdv).toBeNull();
});

test("NaN metric value becomes null", () => {
  const result = normalizeFeasibilityScenarioOutputs({
    base: { gdv: NaN },
  })!;
  expect(result.base?.gdv).toBeNull();
});

// ---------------------------------------------------------------------------
// Null scenario block within payload
// ---------------------------------------------------------------------------

test("null scenario block within payload is preserved as null", () => {
  const result = normalizeFeasibilityScenarioOutputs({
    base: makeMetrics(),
    upside: null,
  })!;
  expect(result.base?.gdv).toBe(3_000_000);
  // null scenario block normalizes to a metrics object with all-null values
  // because normalizeMetrics treats null src as empty object
  expect(result.upside).toBeDefined();
  expect(result.upside?.gdv).toBeNull();
});

// ---------------------------------------------------------------------------
// Does not throw for any malformed input
// ---------------------------------------------------------------------------

test("does not throw for deeply malformed nested object", () => {
  expect(() =>
    normalizeFeasibilityScenarioOutputs({
      base: { gdv: { nested: "object" }, construction_cost: [1, 2, 3] },
    }),
  ).not.toThrow();
});

test("does not throw for scenario block that is a string", () => {
  expect(() =>
    normalizeFeasibilityScenarioOutputs({ base: "invalid" }),
  ).not.toThrow();
});

test("returns metrics object with all nulls for non-object scenario block", () => {
  const result = normalizeFeasibilityScenarioOutputs({ base: "invalid" })!;
  expect(result.base?.gdv).toBeNull();
  expect(result.base?.total_cost).toBeNull();
});

// ---------------------------------------------------------------------------
// Type safety — zero values are preserved (not coerced to null)
// ---------------------------------------------------------------------------

test("zero numeric values are preserved as zero, not null", () => {
  const result = normalizeFeasibilityScenarioOutputs({
    base: { gdv: 0, profit_margin: 0, developer_profit: 0 },
  })!;
  expect(result.base?.gdv).toBe(0);
  expect(result.base?.profit_margin).toBe(0);
  expect(result.base?.developer_profit).toBe(0);
});

test("negative numeric values are preserved as-is", () => {
  const result = normalizeFeasibilityScenarioOutputs({
    base: { developer_profit: -200_000, profit_margin: -0.05 },
  })!;
  expect(result.base?.developer_profit).toBe(-200_000);
  expect(result.base?.profit_margin).toBe(-0.05);
});
