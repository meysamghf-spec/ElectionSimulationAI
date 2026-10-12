import { describe, expect, it } from "vitest";
import { formatNumber, formatPercentagePoints, formatRelativeChange, formatShare } from "@/lib/format";
import { placeholderSpec, preferenceSum, slugify } from "@/lib/spec";

describe("formatters", () => {
  it("keeps percentage points distinct from relative percent", () => {
    expect(formatPercentagePoints(1.5)).toBe("+1.50 pp");
    expect(formatPercentagePoints(-2)).toBe("-2.00 pp");
    expect(formatRelativeChange(0.1)).toBe("+10.00%");
    expect(formatShare(0.5)).toBe("50.00%");
    expect(formatNumber(null)).toBe("—");
  });
});

describe("specification helpers", () => {
  it("does not invent a positive electorate in the placeholder", () => {
    const spec = placeholderSpec();
    expect(spec.empirical_data).toBe(false);
    expect(spec.regions[0].eligible_voters).toBe(0);
    expect(spec.assumptions.some((item) => item.source === "inferred")).toBe(true);
  });

  it("rejects a preference total that is not one without changing it", () => {
    expect(preferenceSum({ a: 0.6, b: 0.6 })).toBeCloseTo(1.2);
  });

  it("builds safe ids", () => {
    expect(slugify("Alice", [])).toBe("alice");
    expect(slugify("Alice", ["alice"])).toBe("alice_2");
    expect(slugify("123", [])).toMatch(/^[a-z]/);
  });
});
