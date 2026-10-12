import { clientAddressFromEdge } from "@/lib/clientAddress";
import { describe, expect, it } from "vitest";

describe("clientAddressFromEdge", () => {
  it("keeps a single address from the edge proxy", () => {
    expect(clientAddressFromEdge("203.0.113.5")).toBe("203.0.113.5");
    expect(clientAddressFromEdge(" 2001:db8::5 ")).toBe("2001:db8::5");
    expect(clientAddressFromEdge("[2001:db8::5]")).toBe("2001:db8::5");
    expect(clientAddressFromEdge("2001:DB8::5")).toBe("2001:db8::5");
  });

  it("drops chains and garbage instead of trusting a client-supplied list", () => {
    expect(clientAddressFromEdge(null)).toBeNull();
    expect(clientAddressFromEdge("")).toBeNull();
    expect(clientAddressFromEdge("203.0.113.5, 198.51.100.2")).toBeNull();
    expect(clientAddressFromEdge("203.0.113.5 198.51.100.2")).toBeNull();
    expect(clientAddressFromEdge("not-an-ip")).toBeNull();
    expect(clientAddressFromEdge("203.0.113.5:443")).toBeNull();
  });
});