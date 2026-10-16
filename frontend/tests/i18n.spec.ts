import { describe, expect, it } from "vitest";
import { directionOf, translate } from "@/lib/i18n";

describe("i18n", () => {
  it("has a Persian string for every key and the right direction", () => {
    expect(directionOf("fa")).toBe("rtl");
    expect(directionOf("en")).toBe("ltr");
    expect(translate("fa", "banner")).toContain("پیش‌بینی واقعی نیستند");
    expect(translate("en", "banner")).toContain("not real predictions");
  });
});
