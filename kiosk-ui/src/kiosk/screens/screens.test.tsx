import { act, fireEvent, render, screen } from "@testing-library/react";
import type { Snapshot } from "../../api";
import { Kiosk } from "../Kiosk";
import { Lines } from "./Lines";

// Valores exactos y acciones de cada botón (mutantes que sobrevivían a Stryker, 2026-10-12).

const agua = { sku: "AGUA", name: "Agua", quantity: 1, unit_price_cents: 250 };
const choco = { sku: "CHOCO", name: "Chocolate", quantity: 2, unit_price_cents: 280 };
const base: Snapshot = {
  state: "SCANNING",
  screen: "W2",
  can_pay: false,
  lines: [],
  total_cents: 0,
  item_count: 0,
  weight: null,
  weight_enabled: false,
  camera: false,
  alert: null,
  seconds_in_state: 0,
  help_pending: false,
  qr_payload: null,
};

/** fetch falso: anota cada POST y responde ok, o falla con `detail` si se pide. */
function stubFetch(fail?: string) {
  const posts: { path: string; body: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((path: string, init?: RequestInit) => {
      posts.push({ path, body: init?.body ? JSON.parse(String(init.body)) : undefined });
      return Promise.resolve(
        fail
          ? new Response(JSON.stringify({ detail: fail }), { status: 409 })
          : new Response(JSON.stringify(base)),
      );
    }),
  );
  return posts;
}

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

async function click(name: string) {
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name }));
  });
}

describe("botones llaman al endpoint correcto", () => {
  it.each([
    ["W2", "CONFIRMAR", "/api/confirm", { lines: [agua], item_count: 1 }],
    ["W2", "CANCELAR COMPRA", "/api/cancel", { lines: [agua], item_count: 1 }],
    ["W3", "PAGAR", "/api/pay", { lines: [agua], item_count: 1, can_pay: true }],
    ["W3", "CORREGIR", "/api/correct", { lines: [agua], item_count: 1 }],
    ["W3", "CANCELAR COMPRA", "/api/cancel", { lines: [agua], item_count: 1 }],
    ["QR", "CANCELAR COMPRA", "/api/cancel", {}],
  ] as [Snapshot["screen"], string, string, Partial<Snapshot>][])("%s · %s → %s", async (scr, button, path, extra) => {
    const posts = stubFetch();
    render(<Kiosk snapshot={{ ...base, screen: scr, ...extra }} />);
    await click(button);
    expect(posts.map((p) => p.path)).toEqual([path]);
  });

  it("«−» quita una unidad de ese producto", async () => {
    const posts = stubFetch();
    render(<Kiosk snapshot={{ ...base, lines: [agua, choco], item_count: 3 }} />);
    await click("Quitar uno de Chocolate");
    expect(posts).toEqual([{ path: "/api/remove", body: { sku: "CHOCO" } }]);
  });
});

describe("errores visibles", () => {
  it.each([
    ["W2", "CONFIRMAR", { lines: [agua], item_count: 1 }],
    ["W3", "PAGAR", { lines: [agua], item_count: 1, can_pay: true }],
    ["QR", "CANCELAR COMPRA", {}],
  ] as [Snapshot["screen"], string, Partial<Snapshot>][])("%s muestra el error de %s", async (scr, button, extra) => {
    stubFetch("No se pudo generar el código QR");
    render(<Kiosk snapshot={{ ...base, screen: scr, ...extra }} />);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    await click(button);
    expect(screen.getByRole("alert")).toHaveTextContent("No se pudo generar el código QR");
  });

  it("W3 muestra la alerta del quiosco solo si la hay", () => {
    const { rerender } = render(<Kiosk snapshot={{ ...base, screen: "W3", lines: [agua], item_count: 1 }} />);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    rerender(<Kiosk snapshot={{ ...base, screen: "W3", lines: [agua], item_count: 1, alert: "Revise su bandeja" }} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Revise su bandeja");
  });
});

describe("sin conexión, CANCELAR y CORREGIR se deshabilitan", () => {
  it.each(["W2", "W3", "QR"] as const)("%s", (scr) => {
    render(<Kiosk snapshot={{ ...base, screen: scr, lines: [agua], item_count: 1 }} connected={false} />);
    expect(screen.getByRole("button", { name: "CANCELAR COMPRA" })).toBeDisabled();
  });

  it("y el «−» también", () => {
    render(<Kiosk snapshot={{ ...base, lines: [agua], item_count: 1 }} connected={false} />);
    expect(screen.getByRole("button", { name: "Quitar uno de Agua" })).toBeDisabled();
  });
});

describe("W2 en vivo", () => {
  it("marca «+ Agregado» lo que acaba de sumarse y la quita a los ~2,4 s", () => {
    vi.useFakeTimers();
    const { rerender } = render(<Kiosk snapshot={{ ...base, lines: [agua], item_count: 1 }} />);
    expect(screen.queryByText("+ Agregado")).not.toBeInTheDocument();

    rerender(<Kiosk snapshot={{ ...base, lines: [agua, { ...choco, quantity: 1 }], item_count: 2 }} />);
    expect(screen.getAllByText("+ Agregado")).toHaveLength(1);
    expect(screen.getByText("Chocolate").closest("li")).toHaveClass("added");
    expect(screen.getByText("Agua").closest("li")).not.toHaveClass("added");

    // Otra unidad del mismo producto también se marca; quitar una no.
    rerender(<Kiosk snapshot={{ ...base, lines: [agua, choco], item_count: 3 }} />);
    rerender(<Kiosk snapshot={{ ...base, lines: [choco], item_count: 2 }} />);
    expect(screen.getAllByText("+ Agregado")).toHaveLength(1);

    act(() => vi.advanceTimersByTime(2100));
    expect(screen.getByText("+ Agregado")).toBeInTheDocument();
    act(() => vi.advanceTimersByTime(400));
    expect(screen.queryByText("+ Agregado")).not.toBeInTheDocument();
  });

  it("vacío: sin pista de «siguiente producto» y CONFIRMAR deshabilitado", () => {
    render(<Kiosk snapshot={base} />);
    expect(screen.queryByText(/Pasa el siguiente producto/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "CONFIRMAR" })).toBeDisabled();
  });

  it("con alerta: no muestra la pista y bloquea CONFIRMAR", () => {
    render(<Kiosk snapshot={{ ...base, lines: [agua], item_count: 1, alert: "Hay un producto que no reconocemos" }} />);
    expect(screen.queryByText(/Pasa el siguiente producto/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "CONFIRMAR" })).toBeDisabled();
  });

  it("con balanza y peso correcto no muestra «Pesando…» y deja CONFIRMAR", () => {
    render(<Kiosk snapshot={{ ...base, lines: [agua], item_count: 1, weight_enabled: true, weight: { ok: true, diff_g: 0 } }} />);
    expect(screen.queryByText("Pesando la bandeja…")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "CONFIRMAR" })).toBeEnabled();
  });
});

describe("Lines", () => {
  it("precio unitario por defecto y subtotal por línea cuando se pide", () => {
    const { rerender } = render(<Lines snapshot={{ ...base, lines: [choco] }} />);
    expect(screen.getByText("S/ 2.80")).toBeInTheDocument();
    rerender(<Lines snapshot={{ ...base, lines: [choco] }} subtotal />);
    expect(screen.getByText("S/ 5.60")).toBeInTheDocument();
  });

  it("sin onRemove no hay botón «−» ni clase removable", () => {
    render(<Lines snapshot={{ ...base, lines: [agua] }} />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(screen.getByText("Agua").closest("li")).not.toHaveClass("removable");
  });
});

describe("QR", () => {
  it("la cuenta atrás nunca baja de 0", () => {
    render(<Kiosk snapshot={{ ...base, screen: "QR", seconds_in_state: 150 }} />);
    expect(screen.getByText("0 s")).toBeInTheDocument();
  });

  it("redondea hacia arriba los segundos que quedan", () => {
    render(<Kiosk snapshot={{ ...base, screen: "QR", seconds_in_state: 0.4 }} />);
    expect(screen.getByText("120 s")).toBeInTheDocument();
  });

  it("al cambiar el enlace de pago no muestra el QR anterior", async () => {
    const { rerender } = render(<Kiosk snapshot={{ ...base, screen: "QR", qr_payload: "https://localhost:8443/pay/ch_1" }} />);
    const first = (await screen.findByRole("img", { name: "Código QR de pago" })).getAttribute("src");
    rerender(<Kiosk snapshot={{ ...base, screen: "QR", qr_payload: "https://localhost:8443/pay/ch_2" }} />);
    const img = await screen.findByRole("img", { name: "Código QR de pago" });
    await vi.waitFor(() => expect(img.getAttribute("src")).not.toBe(first));
    expect(img.getAttribute("src")).toMatch(/^data:image\/png;base64,/);
  });
});
