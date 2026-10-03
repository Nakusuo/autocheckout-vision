import { render, screen } from "@testing-library/react";
import { Kiosk } from "./Kiosk";
import type { Snapshot } from "../api";

const base: Snapshot = {
  state: "IDLE",
  screen: "W1",
  can_pay: false,
  lines: [],
  total_cents: 0,
  item_count: 0,
  weight: null,
  alert: null,
  seconds_in_state: 0,
  help_pending: false,
};
const agua = { sku: "AGUA", name: "Agua", quantity: 1, unit_price_cents: 250 };

describe("Kiosk", () => {
  it("W1 muestra el texto y el botón INICIAR", () => {
    render(<Kiosk snapshot={base} />);
    expect(screen.getByText("[AUTO-CHECKOUT] Coloca tus productos")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "INICIAR" })).toBeInTheDocument();
  });

  it("W2 muestra la línea y CONFIRMAR; deshabilitado sin productos", () => {
    const snap = { ...base, screen: "W2" as const, lines: [agua], total_cents: 250, item_count: 1 };
    const { rerender } = render(<Kiosk snapshot={snap} />);
    expect(screen.getByText("Agua")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getAllByText("S/ 2.50").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "CONFIRMAR" })).toBeEnabled();
    rerender(<Kiosk snapshot={{ ...snap, lines: [], item_count: 0, total_cents: 0 }} />);
    expect(screen.getByRole("button", { name: "CONFIRMAR" })).toBeDisabled();
  });

  it("W3 con alerta deshabilita PAGAR y deja CORREGIR", () => {
    const snap = { ...base, screen: "W3" as const, lines: [agua], item_count: 1, alert: "Revise su bandeja" };
    render(<Kiosk snapshot={snap} />);
    expect(screen.getByText("Revise su bandeja")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "PAGAR" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "CORREGIR" })).toBeEnabled();
  });

  it("W3 con can_pay habilita PAGAR", () => {
    const snap = { ...base, screen: "W3" as const, lines: [agua], item_count: 1, can_pay: true };
    render(<Kiosk snapshot={snap} />);
    expect(screen.getByRole("button", { name: "PAGAR" })).toBeEnabled();
  });

  it.each(["W1", "W2", "W3"] as const)("SOLICITAR AYUDA visible en %s", (screen_) => {
    render(<Kiosk snapshot={{ ...base, screen: screen_ }} />);
    expect(screen.getByRole("button", { name: "SOLICITAR AYUDA" })).toBeInTheDocument();
  });
});
