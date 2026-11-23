import { act, fireEvent, render, renderHook, screen, waitFor } from "@testing-library/react";
import { useKioskState, type Snapshot } from "../api";
import { AyudaPanel } from "./AyudaPanel";

/** WebSocket falso: las pruebas abren, cierran y empujan mensajes a mano. */
class FakeSocket {
  static all: FakeSocket[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((ev: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  url: string;
  constructor(url: string) {
    this.url = url;
    FakeSocket.all.push(this);
  }
  close() {
    this.onclose?.();
  }
  open() {
    act(() => this.onopen?.());
  }
  send(data: unknown) {
    act(() => this.onmessage?.({ data: typeof data === "string" ? data : JSON.stringify(data) }));
  }
  drop() {
    act(() => this.onclose?.());
  }
}

const snap: Snapshot = {
  state: "SCANNING",
  screen: "W2",
  can_pay: false,
  lines: [{ sku: "AGUA", name: "Agua", quantity: 1, unit_price_cents: 250 }],
  total_cents: 250,
  item_count: 1,
  weight: null,
  weight_enabled: false,
  camera: false,
  alert: null,
  seconds_in_state: 0,
  help_pending: false,
  qr_payload: null,
};

type Route = (method: string, path: string) => unknown;

const alertRoutes = new WeakSet<Route>();

function stubFetch(route: Route) {
  const calls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      const method = init?.method ?? "GET";
      calls.push(`${method} ${url}`);
      // Las alertas solo las responde quien las pide; las demás pruebas no tienen ninguna
      const body = url.startsWith("/api/alerts") && !alertRoutes.has(route) ? [] : route(method, url);
      return Promise.resolve(new Response(JSON.stringify(body ?? {})));
    }),
  );
  return calls;
}

beforeEach(() => {
  FakeSocket.all = [];
  vi.stubGlobal("WebSocket", FakeSocket);
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("useKioskState", () => {
  it("recibe el estado, ignora mensajes rotos y se reconecta al caerse", () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useKioskState());
    const [first] = FakeSocket.all;
    first.open();
    first.send(snap);
    expect(result.current).toEqual({ snapshot: snap, connected: true });

    first.send("{no es json");
    first.send({ ...snap, screen: "W9", total_cents: "mucho" });
    expect(result.current.snapshot).toEqual(snap);

    first.drop();
    expect(result.current.connected).toBe(false);
    expect(FakeSocket.all).toHaveLength(1);
    act(() => vi.advanceTimersByTime(1000));
    expect(FakeSocket.all).toHaveLength(2);
    FakeSocket.all[1].open();
    expect(result.current.connected).toBe(true);
  });

  it("con la pantalla oculta cierra la conexión y la abre al volver (Cloud Run cobra por conexión)", () => {
    vi.useFakeTimers();
    let hidden = false;
    vi.spyOn(document, "hidden", "get").mockImplementation(() => hidden);
    const { result } = renderHook(() => useKioskState());
    FakeSocket.all[0].open();
    expect(result.current.connected).toBe(true);

    hidden = true;
    act(() => document.dispatchEvent(new Event("visibilitychange")));
    expect(result.current.connected).toBe(false);
    act(() => vi.advanceTimersByTime(5000));
    expect(FakeSocket.all).toHaveLength(1); // oculta: no reintenta

    hidden = false;
    act(() => document.dispatchEvent(new Event("visibilitychange")));
    expect(FakeSocket.all).toHaveLength(2);
    FakeSocket.all[1].open();
    expect(result.current.connected).toBe(true);
    vi.restoreAllMocks();
  });

  it("al desmontar no intenta reconectarse", () => {
    vi.useFakeTimers();
    const { unmount } = renderHook(() => useKioskState());
    unmount();
    act(() => vi.advanceTimersByTime(5000));
    expect(FakeSocket.all).toHaveLength(1);
  });
});

const noSales = { count: 0, total_cents: 0, receipts: [] };

/** AudioContext falso: cuenta los osciladores que arrancan. */
function stubAudio() {
  const starts = { n: 0 };
  class FakeAudio {
    currentTime = 0;
    destination = {};
    createOscillator() {
      return { type: "", frequency: { value: 0 }, connect() {}, start: () => void starts.n++, stop() {} };
    }
    createGain() {
      return { gain: { value: 0 }, connect() {} };
    }
    close() {
      return Promise.resolve();
    }
  }
  vi.stubGlobal("AudioContext", FakeAudio);
  return starts;
}

describe("AyudaPanel sonido", () => {
  beforeEach(() => localStorage.clear());

  it("pita cuando llega una solicitud nueva", async () => {
    const starts = stubAudio();
    let pending: { id: number; screen: string; at: number }[] = [];
    stubFetch((_m, path) => (path === "/api/sales" ? noSales : pending));
    vi.useFakeTimers({ shouldAdvanceTime: true });
    render(<AyudaPanel />);
    await screen.findByText("Sin solicitudes");
    expect(starts.n).toBe(0);
    pending = [{ id: 3, screen: "W2", at: 0 }];
    await act(() => vi.advanceTimersByTimeAsync(2000));
    expect(await screen.findByText(/Solicitud #3/)).toBeInTheDocument();
    expect(starts.n).toBe(2);
    await act(() => vi.advanceTimersByTimeAsync(2000));
    expect(starts.n).toBe(2);
  });

  it("con el sonido apagado no pita y recuerda la elección", async () => {
    const starts = stubAudio();
    let pending: { id: number; screen: string; at: number }[] = [];
    stubFetch((_m, path) => (path === "/api/sales" ? noSales : pending));
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const { unmount } = render(<AyudaPanel />);
    fireEvent.click(screen.getByRole("button", { name: "Sonido: sí" }));
    expect(localStorage.getItem("ayuda.sound")).toBe("off");
    pending = [{ id: 4, screen: "W2", at: 0 }];
    await act(() => vi.advanceTimersByTimeAsync(2000));
    expect(await screen.findByText(/Solicitud #4/)).toBeInTheDocument();
    expect(starts.n).toBe(0);
    unmount();
    render(<AyudaPanel />);
    expect(screen.getByRole("button", { name: "Sonido: no" })).toBeInTheDocument();
  });
});

describe("AyudaPanel", () => {
  it("sin cobro en curso no ofrece aprobar pago ni muestra la compra", async () => {
    stubFetch(() => []);
    render(<AyudaPanel />);
    const ws = FakeSocket.all[0];
    ws.open();
    ws.send(snap);
    expect(await screen.findByText("Sin solicitudes")).toBeInTheDocument();
    expect(screen.queryByText(/Agua/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Aprobar pago/ })).not.toBeInTheDocument();
    expect(screen.getByText(/Sin ventas todavía/)).toBeInTheDocument();
  });

  it("con el cliente en la pantalla de pago, la caja puede aprobarlo", async () => {
    const calls = stubFetch(() => []);
    render(<AyudaPanel />);
    const ws = FakeSocket.all[0];
    ws.open();
    ws.send({ ...snap, state: "PAYING", screen: "QR", total_cents: 150 });
    expect(screen.getByText("Cliente pagando S/ 1.50")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Aprobar pago" }));
    expect(calls).not.toContain("POST /api/caja/accept-payment"); // primero pide confirmar
    fireEvent.click(screen.getByRole("button", { name: "No, volver" }));
    fireEvent.click(screen.getByRole("button", { name: "Aprobar pago" }));
    expect(screen.getByText(/Se emitirá la boleta y no se puede deshacer/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Sí, aprobar S/ 1.50" }));
    await waitFor(() => expect(calls).toContain("POST /api/caja/accept-payment"));
  });

  it("la confirmación pendiente se descarta si el cliente sale del pago", () => {
    stubFetch(() => []);
    render(<AyudaPanel />);
    const ws = FakeSocket.all[0];
    ws.open();
    ws.send({ ...snap, state: "PAYING", screen: "QR", total_cents: 150 });
    fireEvent.click(screen.getByRole("button", { name: "Aprobar pago" }));
    ws.send({ ...snap, state: "IDLE", screen: "W1" });
    ws.send({ ...snap, state: "PAYING", screen: "QR", total_cents: 150 });
    expect(screen.getByRole("button", { name: "Aprobar pago" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Sí, aprobar/ })).not.toBeInTheDocument();
  });

  it("muestra las ventas de hoy con el detalle, quién pagó y cómo", async () => {
    stubFetch((_m, path) =>
      path === "/api/sales"
        ? {
            count: 2,
            total_cents: 430,
            receipts: [
              {
                number: "B001-00000002",
                issued_at: "2026-11-21T04:26:00+00:00",
                items: 1,
                total_cents: 150,
                lines: [{ name: "Glacitas 30 g", quantity: 1 }],
                payer: "Alessandra Rod*",
                method: "Yape (notificación)",
              },
              { number: "B001-00000001", issued_at: "2026-11-21T04:00:00+00:00", items: 2, total_cents: 280 },
            ],
          }
        : [],
    );
    render(<AyudaPanel />);
    expect(await screen.findByText(/1 × Glacitas 30 g/)).toBeInTheDocument();
    expect(screen.getByText(/2 ventas/)).toBeInTheDocument();
    expect(screen.getByText(/Alessandra Rod\*/)).toBeInTheDocument();
    expect(screen.getByText(/Yape \(notificación\)/)).toBeInTheDocument();
    expect(screen.getByText("2 productos")).toBeInTheDocument(); // boleta sin detalle
  });

  it("lista la ayuda pendiente y la marca como atendida", async () => {
    let pending = [{ id: 7, screen: "W2", at: 0 }];
    const calls = stubFetch((method, path) => {
      if (path === "/api/sales") return noSales;
      if (method === "DELETE") pending = [];
      return pending;
    });
    render(<AyudaPanel />);
    expect(await screen.findByText(/Solicitud #7/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Atendido" }));
    expect(await screen.findByText("Sin solicitudes")).toBeInTheDocument();
    expect(calls).toContain("DELETE /api/help/7");
  });

  it("«Reactivar quiosco» aparece solo fuera de servicio y llama a la API", async () => {
    const calls = stubFetch((_m, path) => (path === "/api/sales" ? noSales : []));
    render(<AyudaPanel />);
    const ws = FakeSocket.all[0];
    ws.open();
    ws.send(snap);
    expect(screen.queryByRole("button", { name: "Reactivar quiosco" })).not.toBeInTheDocument();
    ws.send({ ...snap, screen: "FUERA_DE_SERVICIO", state: "OUT_OF_SERVICE" });
    fireEvent.click(screen.getByRole("button", { name: "Reactivar quiosco" }));
    await waitFor(() => expect(calls).toContain("POST /api/recover"));
  });
});

describe("AyudaPanel alertas de seguridad", () => {
  const noSales = { count: 0, total_cents: 0, receipts: [] };
  const alert = { id: 9, reason: "Producto no reconocido frente a la cámara", screen: "W2", at: 0, times: 2, outcome: "pagada" };

  function stubAudio() {
    const starts = { n: 0 };
    class FakeAudio {
      currentTime = 0;
      destination = {};
      createOscillator() {
        return { type: "", frequency: { value: 0 }, connect() {}, start: () => starts.n++, stop() {} };
      }
      createGain() {
        return { gain: { value: 0 }, connect() {} };
      }
      close() {
        return Promise.resolve();
      }
    }
    vi.stubGlobal("AudioContext", FakeAudio);
    return starts;
  }

  it("muestra la alerta, pita y se marca como revisada", async () => {
    localStorage.removeItem("ayuda.sound"); // otra prueba lo dejó apagado
    const starts = stubAudio();
    let alerts = [alert];
    const route: Route = (method, path) => {
      if (path === "/api/sales") return noSales;
      if (path.startsWith("/api/alerts")) {
        if (method === "DELETE") alerts = [];
        return alerts;
      }
      return [];
    };
    alertRoutes.add(route);
    const calls = stubFetch(route);
    render(<AyudaPanel />);
    expect(await screen.findByText(/Producto no reconocido frente a la cámara/)).toBeInTheDocument();
    expect(screen.getByText(/2 veces/)).toBeInTheDocument();
    expect(screen.getByText(/compra pagada/)).toBeInTheDocument();
    expect(starts.n).toBe(2);
    fireEvent.click(screen.getByRole("button", { name: "Revisado" }));
    expect(await screen.findByText(/Sin alertas/)).toBeInTheDocument();
    expect(calls).toContain("DELETE /api/alerts/9");
  });

  it("una sola vez se escribe en singular", async () => {
    const route: Route = (_m, path) =>
      path === "/api/sales" ? noSales : path === "/api/alerts" ? [{ ...alert, times: 1, outcome: "en curso" }] : [];
    alertRoutes.add(route);
    stubFetch(route);
    render(<AyudaPanel />);
    expect(await screen.findByText(/1 vez/)).toBeInTheDocument();
  });
});

describe("AyudaPanel en la nube (clave de caja)", () => {
  beforeEach(() => localStorage.clear());

  it("sin clave pide la clave y luego la manda en cada consulta", async () => {
    const headers: (string | null)[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string, init?: RequestInit) => {
        const key = new Headers(init?.headers).get("X-Caja-Key");
        headers.push(key);
        if (key !== "clave-de-caja-larga") {
          return Promise.resolve(new Response(JSON.stringify({ detail: "Clave de caja inválida" }), { status: 401 }));
        }
        return Promise.resolve(new Response(JSON.stringify(url === "/api/help" ? [{ id: 5, screen: "W2", at: 0 }] : [])));
      }),
    );
    vi.useFakeTimers({ shouldAdvanceTime: true });
    render(<AyudaPanel />);
    expect(await screen.findByText("Clave de caja")).toBeInTheDocument();
    expect(screen.queryByText("Solicitudes de ayuda")).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument(); // no es un error, es la clave
    fireEvent.change(screen.getByLabelText("Clave"), { target: { value: " clave-de-caja-larga " } });
    fireEvent.click(screen.getByRole("button", { name: "Entrar" }));
    await act(() => vi.advanceTimersByTimeAsync(2000));
    expect(await screen.findByText(/Solicitud #5/)).toBeInTheDocument();
    expect(headers.at(-1)).toBe("clave-de-caja-larga");
    expect(localStorage.getItem("ayuda.key")).toBe("clave-de-caja-larga");
  });
});
