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

function stubFetch(route: Route) {
  const calls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      const method = init?.method ?? "GET";
      calls.push(`${method} ${url}`);
      return Promise.resolve(new Response(JSON.stringify(route(method, url) ?? {})));
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

describe("CajaPanel", () => {
  it("lista la ayuda pendiente y la marca como atendida", async () => {
    let pending = [{ id: 7, screen: "W2", at: 0 }];
    const calls = stubFetch((method) => {
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
    const calls = stubFetch(() => []);
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
    stubFetch(() => []);
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
