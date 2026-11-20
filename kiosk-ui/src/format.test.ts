import { formatPEN, groupPhone } from "./format";

describe("formatPEN", () => {
  it("formatea céntimos", () => {
    expect(formatPEN(250)).toBe("S/ 2.50");
    expect(formatPEN(0)).toBe("S/ 0.00");
    expect(formatPEN(1120)).toBe("S/ 11.20");
  });
});

it("agrupa celulares de tres en tres", () => {
  expect(groupPhone("")).toBe("");
  expect(groupPhone("987")).toBe("987");
  expect(groupPhone("9876")).toBe("987 6");
  expect(groupPhone("987654321")).toBe("987 654 321");
});
