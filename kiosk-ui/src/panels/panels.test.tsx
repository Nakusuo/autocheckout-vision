import { act, fireEvent, render, renderHook, screen, waitFor } from "@testing-library/react";
import { useKioskState, type Snapshot } from "../api";
import { CajaPanel } from "./CajaPanel";
import { SimPanel } from "./SimPanel";

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

describe("CajaPanel ventas y sonido", () => {
  beforeEach(() => localStorage.clear());

  it("muestra las ventas del día", async () => {
    stubFetch((_m, path) =>
      path === "/api/sales"
        ? {
            count: 2,
            total_cents: 1250,
            receipts: [
              { number: "B001-00000002", issued_at: new Date(2026, 9, 12, 15, 4).toISOString(), items: 3, total_cents: 1000 },
              { number: "B001-00000001", issued_at: new Date(2026, 9, 12, 9, 30).toISOString(), items: 1, total_cents: 250 },
            ],
          }
        : [],
    );
    render(<CajaPanel />);
    expect(await screen.findByText("B001-00000002", { exact: false })).toBeInTheDocument();
    expect(screen.getByText("2 ventas")).toBeInTheDocument();
    expect(screen.getByText(/15:04/)).toHaveTextContent("3 productos");
    expect(screen.getByText(/09:30/)).toHaveTextContent("1 producto");
  });

  it("sin ventas muestra el estado vacío", async () => {
    stubFetch((_m, path) => (path === "/api/sales" ? noSales : []));
    render(<CajaPanel />);
    expect(await screen.findByText("Aún no hay ventas hoy.")).toBeInTheDocument();
  });

  it("pita cuando llega una solicitud nueva", async () => {
    const starts = stubAudio();
    let pending: { id: number; screen: string; at: number }[] = [];
    stubFetch((_m, path) => (path === "/api/sales" ? noSales : pending));
    vi.useFakeTimers({ shouldAdvanceTime: true });
    render(<CajaPanel />);
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
    const { unmount } = render(<CajaPanel />);
    fireEvent.click(screen.getByRole("button", { name: "Sonido: sí" }));
    expect(localStorage.getItem("caja.sound")).toBe("off");
    pending = [{ id: 4, screen: "W2", at: 0 }];
    await act(() => vi.advanceTimersByTimeAsync(2000));
    expect(await screen.findByText(/Solicitud #4/)).toBeInTheDocument();
    expect(starts.n).toBe(0);
    unmount();
    render(<CajaPanel />);
    expect(screen.getByRole("button", { name: "Sonido: no" })).toBeInTheDocument();
  });
});

describe("CajaPanel", () => {
  it("lista la ayuda pendiente y la marca como atendida", async () => {
    let pending = [{ id: 7, screen: "W2", at: 0 }];
    const calls = stubFetch((method, path) => {
      if (path === "/api/sales") return noSales;
      if (method === "DELETE") pending = [];
      return pending;
    });
    render(<CajaPanel />);
    expect(await screen.findByText(/Solicitud #7/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Atendido" }));
    expect(await screen.findByText("Sin solicitudes")).toBeInTheDocument();
    expect(calls).toContain("DELETE /api/help/7");
  });

  it("«Recalibrar cámara» solo aparece con cámara y llama a la API", async () => {
    const calls = stubFetch((_m, path) => (path === "/api/sales" ? noSales : []));
    render(<CajaPanel />);
    const ws = FakeSocket.all[0];
    ws.open();
    ws.send(snap);
    expect(screen.queryByRole("button", { name: "Recalibrar cámara" })).not.toBeInTheDocument();

    ws.send({ ...snap, camera: true });
    fireEvent.click(screen.getByRole("button", { name: "Recalibrar cámara" }));
    expect(await screen.findByRole("button", { name: "Calibrando…" })).toBeDisabled();
    expect(calls).toContain("POST /api/recalibrate");
  });

  it("«Reactivar quiosco» solo se habilita fuera de servicio", async () => {
    stubFetch((_m, path) => (path === "/api/sales" ? noSales : []));
    render(<CajaPanel />);
    const ws = FakeSocket.all[0];
    ws.open();
    ws.send(snap);
    expect(screen.getByRole("button", { name: "Reactivar quiosco" })).toBeDisabled();
    ws.send({ ...snap, screen: "FUERA_DE_SERVICIO", state: "OUT_OF_SERVICE" });
    expect(screen.getByRole("button", { name: "Reactivar quiosco" })).toBeEnabled();
  });
});

describe("SimPanel", () => {
  const catalog = [{ sku: "AGUA", name: "Agua", price_cents: 250, weight_g: 651 }];

  it("sin balanza oculta «Sin escanear»; pasar por la cámara llama a /sim/scan", async () => {
    const calls = stubFetch((_m, path) =>
      path === "/sim/catalog" ? catalog : path.startsWith("/sim/") ? { tray: [], camera: [] } : snap,
    );
    render(<SimPanel />);
    const ws = FakeSocket.all[0];
    ws.open();
    ws.send(snap);
    fireEvent.click(await screen.findByRole("button", { name: "Pasar por la cámara" }));
    await waitFor(() => expect(calls).toContain("POST /sim/scan"));
    expect(screen.queryByRole("button", { name: "Sin escanear" })).not.toBeInTheDocument();

    ws.send({ ...snap, weight_enabled: true });
    expect(screen.getByRole("button", { name: "Sin escanear" })).toBeInTheDocument();
  });
});

describe("CajaPanel alertas de seguridad", () => {
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
    localStorage.removeItem("caja.sound"); // otra prueba lo dejó apagado
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
    render(<CajaPanel />);
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
    render(<CajaPanel />);
    expect(await screen.findByText(/1 vez/)).toBeInTheDocument();
  });
});
