import { formatDateTime, formatPEN, groupPhone } from "./format";

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

it("muestra la fecha de la boleta en hora de Lima", () => {
  expect(formatDateTime("2026-11-20T02:05:00+00:00")).toBe("19/11/2026, 21:05");
  expect(formatDateTime("no es fecha")).toBe("no es fecha");
});
