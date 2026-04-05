/**
 * Tests for format-utils.ts — shared currency formatting helpers.
 *
 * Validates:
 *  - formatCurrencyPrecise: AED and non-AED currencies, negative values
 *  - formatCurrency: AED compact format, non-AED delegation to formatAmount
 *  - formatAmount: AED compact, non-AED via Intl.NumberFormat
 *  - formatAdjustment: positive/negative/zero for AED and non-AED
 *  - formatCurrencyMap: empty map, single currency, multi-currency, compact option
 */

import {
  formatCurrencyPrecise,
  formatCurrency,
  formatAmount,
  formatAdjustment,
  formatCurrencyMap,
} from "@/lib/format-utils";

// ---------------------------------------------------------------------------
// formatCurrencyPrecise
// ---------------------------------------------------------------------------

describe("formatCurrencyPrecise", () => {
  it("formats positive AED value without compacting", () => {
    expect(formatCurrencyPrecise(3_000)).toBe("AED 3,000");
  });

  it("formats negative AED value", () => {
    expect(formatCurrencyPrecise(-1_500)).toBe("AED -1,500");
  });

  it("formats zero AED value", () => {
    expect(formatCurrencyPrecise(0)).toBe("AED 0");
  });

  it("does not compact millions for AED", () => {
    expect(formatCurrencyPrecise(2_000_000)).toBe("AED 2,000,000");
  });

  it("formats non-AED currency (USD) via Intl.NumberFormat", () => {
    const result = formatCurrencyPrecise(3_000, "USD");
    expect(result).toMatch(/\$3,000/);
  });

  it("formats non-AED currency (JOD) via Intl.NumberFormat", () => {
    const result = formatCurrencyPrecise(1_500, "JOD");
    // Intl formats JOD with its symbol
    expect(result).toMatch(/1,500/);
  });

  it("defaults to AED when no currency argument is provided", () => {
    expect(formatCurrencyPrecise(5_000)).toBe("AED 5,000");
  });
});

// ---------------------------------------------------------------------------
// formatCurrency
// ---------------------------------------------------------------------------

describe("formatCurrency", () => {
  it("compacts millions for AED", () => {
    expect(formatCurrency(1_500_000)).toBe("AED 1.5M");
  });

  it("compacts thousands for AED", () => {
    expect(formatCurrency(150_000)).toBe("AED 150K");
  });

  it("formats small AED values without compacting", () => {
    expect(formatCurrency(500)).toBe("AED 500");
  });

  it("handles negative AED millions symmetrically", () => {
    expect(formatCurrency(-1_500_000)).toBe("AED -1.5M");
  });

  it("handles negative AED thousands symmetrically", () => {
    expect(formatCurrency(-150_000)).toBe("AED -150K");
  });

  it("delegates non-AED currency to formatAmount", () => {
    const result = formatCurrency(500_000, "USD");
    expect(result).toMatch(/\$500,000/);
  });

  it("delegates non-AED currency (JOD) to formatAmount", () => {
    const result = formatCurrency(200_000, "JOD");
    expect(result).toMatch(/200,000/);
  });

  it("defaults to AED when no currency argument is provided", () => {
    expect(formatCurrency(2_000_000)).toBe("AED 2.0M");
  });
});

// ---------------------------------------------------------------------------
// formatAmount
// ---------------------------------------------------------------------------

describe("formatAmount", () => {
  it("uses compact AED format for AED currency", () => {
    expect(formatAmount(525_000, "AED")).toBe("AED 525K");
  });

  it("uses Intl for USD currency", () => {
    const result = formatAmount(525_000, "USD");
    expect(result).toMatch(/\$525,000/);
  });

  it("formats negative USD value", () => {
    const result = formatAmount(-5_000, "USD");
    expect(result).toMatch(/5,000/);
  });
});

// ---------------------------------------------------------------------------
// formatAdjustment
// ---------------------------------------------------------------------------

describe("formatAdjustment", () => {
  it("formats positive AED adjustment with + sign", () => {
    expect(formatAdjustment(25_000, "AED")).toBe("AED +25K");
  });

  it("formats negative AED adjustment with - sign", () => {
    expect(formatAdjustment(-5_000, "AED")).toBe("AED -5K");
  });

  it("formats zero adjustment", () => {
    expect(formatAdjustment(0, "AED")).toBe("AED 0");
  });

  it("prepends sign for non-AED positive adjustment", () => {
    const result = formatAdjustment(25_000, "USD");
    expect(result).toMatch(/^\+/);
    expect(result).toMatch(/25,000/);
  });

  it("prepends sign for non-AED negative adjustment", () => {
    const result = formatAdjustment(-25_000, "USD");
    expect(result).toMatch(/^-/);
    expect(result).toMatch(/25,000/);
  });
});

// ---------------------------------------------------------------------------
// formatCurrencyMap
// ---------------------------------------------------------------------------

describe("formatCurrencyMap", () => {
  it("returns '—' for an empty map", () => {
    expect(formatCurrencyMap({})).toBe("—");
  });

  it("returns '—' when all values are zero", () => {
    expect(formatCurrencyMap({ AED: 0, USD: 0 })).toBe("—");
  });

  it("formats a single-currency AED map", () => {
    const result = formatCurrencyMap({ AED: 5_000_000 });
    expect(result).toBe("AED 5.0M");
  });

  it("formats a single-currency USD map", () => {
    const result = formatCurrencyMap({ USD: 1_200_000 });
    expect(result).toMatch(/\$1,200,000/);
  });

  it("formats a multi-currency map with ' / ' separator", () => {
    const result = formatCurrencyMap({ AED: 5_000_000, USD: 1_200_000 });
    expect(result).toContain("AED 5.0M");
    expect(result).toContain(" / ");
    expect(result).toMatch(/\$1,200,000/);
  });

  it("excludes zero-value currencies from multi-currency output", () => {
    const result = formatCurrencyMap({ AED: 5_000_000, USD: 0 });
    expect(result).toBe("AED 5.0M");
    expect(result).not.toContain(" / ");
  });

  it("uses precise (non-compact) format when compact:false", () => {
    const result = formatCurrencyMap({ AED: 5_000_000 }, { compact: false });
    expect(result).toBe("AED 5,000,000");
  });
});
