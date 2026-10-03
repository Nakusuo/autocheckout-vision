import { formatPEN } from "./format";

describe("formatPEN", () => {
  it("formatea céntimos", () => {
    expect(formatPEN(250)).toBe("S/ 2.50");
    expect(formatPEN(0)).toBe("S/ 0.00");
    expect(formatPEN(1120)).toBe("S/ 11.20");
  });
});
