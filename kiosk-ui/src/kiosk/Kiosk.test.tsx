import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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
  qr_payload: null,
};
const agua = { sku: "AGUA", name: "Agua", quantity: 1, unit_price_cents: 250 };

describe("Kiosk", () => {
  it("W1 muestra el texto y el botón INICIAR", () => {
    render(<Kiosk snapshot={base} />);
    expect(screen.getByRole("heading", { name: "[AUTO-CHECKOUT] Coloca tus productos" })).toBeInTheDocument();
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

  it("Ayuda en camino solo si help_pending", () => {
    const { rerender } = render(<Kiosk snapshot={base} />);
    expect(screen.queryByText("Ayuda en camino")).not.toBeInTheDocument();
    rerender(<Kiosk snapshot={{ ...base, help_pending: true }} />);
    expect(screen.getByRole("status")).toHaveTextContent("Ayuda en camino");
  });

  it("sin conexión avisa y deshabilita las acciones, no la ayuda", () => {
    const w3 = { ...base, screen: "W3" as const, lines: [agua], item_count: 1, can_pay: true };
    const { rerender } = render(<Kiosk snapshot={w3} connected={false} />);
    expect(screen.getByRole("status")).toHaveTextContent("Reconectando…");
    expect(screen.getByRole("button", { name: "PAGAR" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "CORREGIR" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "SOLICITAR AYUDA" })).toBeEnabled();
    rerender(<Kiosk snapshot={{ ...w3, screen: "W2" }} connected={false} />);
    expect(screen.getByRole("button", { name: "CONFIRMAR" })).toBeDisabled();
    rerender(<Kiosk snapshot={base} connected={false} />);
    expect(screen.getByRole("button", { name: "INICIAR" })).toBeDisabled();
  });

  it("bloquea el botón mientras la petición está en curso", async () => {
    let resolve!: (r: Response) => void;
    const fetchMock = vi.fn(() => new Promise<Response>((r) => (resolve = r)));
    vi.stubGlobal("fetch", fetchMock);
    render(<Kiosk snapshot={base} />);
    const btn = screen.getByRole("button", { name: "INICIAR" });
    fireEvent.click(btn);
    expect(btn).toBeDisabled();
    fireEvent.click(btn);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    resolve(new Response(JSON.stringify(base)));
    await waitFor(() => expect(btn).toBeEnabled());
    vi.unstubAllGlobals();
  });

  it("error de red muestra mensaje claro", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.reject(new TypeError("fail"))));
    render(<Kiosk snapshot={base} />);
    fireEvent.click(screen.getByRole("button", { name: "INICIAR" }));
    expect(await screen.findByText("No se pudo conectar. Intente de nuevo")).toBeInTheDocument();
    vi.unstubAllGlobals();
  });

  it("QR muestra monto, espera y segundos restantes", () => {
    render(<Kiosk snapshot={{ ...base, screen: "QR", total_cents: 530, seconds_in_state: 20 }} />);
    expect(screen.getByText("S/ 5.30")).toBeInTheDocument();
    expect(screen.getByText("Esperando confirmación del pago")).toBeInTheDocument();
    expect(screen.getByText("100 s")).toBeInTheDocument();
  });

  it("W4 muestra agradecimiento, total y cuenta atrás", () => {
    const snap = { ...base, screen: "W4" as const, lines: [agua], item_count: 1, total_cents: 250, seconds_in_state: 3 };
    render(<Kiosk snapshot={snap} />);
    expect(screen.getByText("Gracias por su compra")).toBeInTheDocument();
    expect(screen.getByText("Agua")).toBeInTheDocument();
    expect(screen.getAllByText("S/ 2.50").length).toBeGreaterThan(0);
    expect(screen.getByText("Volviendo al inicio en 7 s")).toBeInTheDocument();
  });

  it("FUERA_DE_SERVICIO avisa y mantiene la ayuda", () => {
    render(<Kiosk snapshot={{ ...base, screen: "FUERA_DE_SERVICIO" }} />);
    expect(screen.getByText("Fuera de servicio")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "SOLICITAR AYUDA" })).toBeInTheDocument();
  });

  it("QR con payload muestra la imagen y la indicación", async () => {
    render(<Kiosk snapshot={{ ...base, screen: "QR", qr_payload: "https://localhost:8443/pay/ch_1" }} />);
    expect(await screen.findByRole("img", { name: "Código QR de pago" })).toBeInTheDocument();
    expect(screen.getByText("Escanea con Yape o Plin")).toBeInTheDocument();
  });

  it("QR sin payload muestra Generando y ninguna imagen", () => {
    render(<Kiosk snapshot={{ ...base, screen: "QR", qr_payload: null }} />);
    expect(screen.getByText("Generando código QR…")).toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });
});
