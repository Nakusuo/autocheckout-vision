import { act, fireEvent, render, screen, within } from "@testing-library/react";
import type { Snapshot } from "../../api";
import { CamaraWeb } from "./CamaraWeb";
import { Escaneo } from "./Escaneo";
import { PagoQrPropio } from "./PagoQrPropio";
import { Ticket } from "./Ticket";

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
  seconds_in_state: 10,
  help_pending: false,
  qr_payload: null,
  payment_method: "yape-qr",
  wallet_qr: "/api/pay/wallet-qr",
  browser_camera: true,
  receipt: null,
};

afterEach(() => {
  vi.unstubAllGlobals();
  Object.defineProperty(navigator, "mediaDevices", { value: undefined, configurable: true });
});

function stubCamera(getUserMedia: () => Promise<unknown>) {
  Object.defineProperty(navigator, "mediaDevices", { value: { getUserMedia }, configurable: true });
}

describe("CamaraWeb", () => {
  it("sin cámara en el navegador lo dice", () => {
    render(<CamaraWeb disabled={false} onAdd={async () => true} />);
    expect(screen.getByRole("alert")).toHaveTextContent("no permite usar la cámara");
    expect(screen.getByText("Pon un producto dentro del visor: la cámara lo reconoce sola.")).toBeInTheDocument();
  });

  it("si el permiso se niega, pide permitir el acceso", async () => {
    stubCamera(() => Promise.reject(new Error("NotAllowed")));
    render(<CamaraWeb disabled={false} onAdd={async () => true} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Permite el acceso");
  });

  it("muestra la vista en vivo y apaga la cámara al salir", async () => {
    const stop = vi.fn();
    const stream = { getTracks: () => [{ stop }] };
    stubCamera(() => Promise.resolve(stream));
    const { unmount } = render(<CamaraWeb disabled={false} onAdd={async () => true} />);
    const video = screen.getByLabelText("Vista de la cámara") as HTMLVideoElement;
    await act(async () => undefined);
    expect(video.srcObject).toBe(stream);
    unmount();
    expect(stop).toHaveBeenCalled();
  });

  it("si la cámara llega después de salir, se apaga enseguida", async () => {
    const stop = vi.fn();
    let resolve!: (s: unknown) => void;
    stubCamera(() => new Promise((r) => (resolve = r)));
    const { unmount } = render(<CamaraWeb disabled={false} onAdd={async () => true} />);
    unmount();
    await act(async () => resolve({ getTracks: () => [{ stop }] }));
    expect(stop).toHaveBeenCalled();
  });
});

describe("CamaraWeb: agregado automático", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  /** Cámara y servidor simulados: cada cuadro responde con el siguiente SKU de la lista. */
  function stubFrames(answers: (string | null)[]) {
    stubCamera(() => Promise.resolve({ getTracks: () => [] }));
    vi.spyOn(HTMLVideoElement.prototype, "videoWidth", "get").mockReturnValue(640);
    vi.spyOn(HTMLVideoElement.prototype, "videoHeight", "get").mockReturnValue(480);
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({ drawImage: () => undefined } as never);
    vi.spyOn(HTMLCanvasElement.prototype, "toBlob").mockImplementation((cb) => cb(new Blob(["x"])));
    const fetch = vi.fn(async () => {
      const sku = answers.shift() ?? null;
      const body = sku ? { match: true, sku, name: `Producto ${sku}`, price_cents: 150 } : { match: false };
      return { ok: true, json: async () => body } as Response;
    });
    vi.stubGlobal("fetch", fetch);
    return fetch;
  }

  async function frames(n: number) {
    for (let i = 0; i < n; i++) await act(async () => vi.advanceTimersByTime(400));
  }

  it("agrega solo tras verlo igual 3 veces y avisa «Agregado»", async () => {
    vi.useFakeTimers();
    stubFrames(["CASINO-43", "CASINO-43", "CASINO-43", "CASINO-43"]);
    const onAdd = vi.fn(async () => true);
    render(<CamaraWeb disabled={false} onAdd={onAdd} />);
    await frames(2);
    expect(within(screen.getByRole("status")).getByText("Producto CASINO-43")).toBeInTheDocument();
    expect(screen.getByText("Mantenlo quieto…")).toBeInTheDocument();
    // El visor muestra la etiqueta con nombre y precio, y las esquinas van cerrándose (2 de 3)
    const box = document.querySelector<HTMLElement>(".webcam-box")!;
    expect(box.querySelector(".ar-tag")).toHaveTextContent("Producto CASINO-43");
    expect(box.style.getPropertyValue("--p")).toBe(String(2 / 3));
    expect(onAdd).not.toHaveBeenCalled();
    await frames(2);
    expect(onAdd).toHaveBeenCalledTimes(1);
    expect(onAdd).toHaveBeenCalledWith("CASINO-43");
    expect(screen.getByText("Agregado: Producto CASINO-43")).toBeInTheDocument();
    expect(document.querySelector(".webcam-box .box-check")).not.toBeNull();
  });

  it("deshabilitada (sin conexión o agregando) no agrega nada", async () => {
    vi.useFakeTimers();
    const fetch = stubFrames([]);
    fetch.mockClear();
    const onAdd = vi.fn(async () => true);
    render(<CamaraWeb disabled onAdd={onAdd} />);
    await frames(5);
    expect(onAdd).not.toHaveBeenCalled();
    expect(fetch).not.toHaveBeenCalled(); // ni siquiera manda cuadros
    expect(screen.getByText("Pon un producto dentro del visor: la cámara lo reconoce sola.")).toBeInTheDocument();
  });

  it("no agrega dos veces si la API tarda mientras el producto sigue en el recuadro", async () => {
    vi.useFakeTimers();
    stubFrames(Array(12).fill("CASINO-43"));
    const onAdd = vi.fn(async () => true);
    const { rerender } = render(<CamaraWeb disabled={false} onAdd={onAdd} />);
    await frames(3);
    expect(onAdd).toHaveBeenCalledTimes(1);
    rerender(<CamaraWeb disabled onAdd={onAdd} />); // agregando: la petición tarda
    await frames(4);
    rerender(<CamaraWeb disabled={false} onAdd={onAdd} />);
    await frames(4);
    expect(onAdd).toHaveBeenCalledTimes(1);
  });

  it("si la API rechaza el producto no dice «Agregado»", async () => {
    vi.useFakeTimers();
    stubFrames(Array(4).fill("CASINO-43"));
    const onAdd = vi.fn(async () => false);
    render(<CamaraWeb disabled={false} onAdd={onAdd} />);
    await frames(4);
    expect(onAdd).toHaveBeenCalledTimes(1);
    expect(screen.queryByText(/Agregado:/)).not.toBeInTheDocument();
  });
});

describe("Escaneo con la cámara del navegador", () => {
  it("muestra la cámara en vez de la bandeja", () => {
    render(<Escaneo snapshot={base} offline={false} />);
    expect(screen.getByText("Pon un producto dentro del visor: la cámara lo reconoce sola.")).toBeInTheDocument();
    expect(screen.queryByText(/Pasa tus productos uno por uno/)).not.toBeInTheDocument();
    // Lista vacía: en horizontal se ve junto a la cámara (en vertical el CSS la oculta).
    expect(screen.getByText(/Tu lista está vacía/)).toBeInTheDocument();
  });

  it("CONFIRMAR y CANCELAR van juntos y CONFIRMAR espera un producto", () => {
    render(<Escaneo snapshot={base} offline={false} />);
    const confirm = screen.getByRole("button", { name: "CONFIRMAR" });
    expect(confirm).toBeDisabled();
    expect(confirm.parentElement).toBe(screen.getByRole("button", { name: "CANCELAR COMPRA" }).parentElement);
  });

  it("con productos, mantiene la cámara y la lista", () => {
    const lines = [{ sku: "CASINO-43", name: "Galletas Casino 43 g", quantity: 1, unit_price_cents: 150 }];
    render(<Escaneo snapshot={{ ...base, lines, item_count: 1, total_cents: 150 }} offline={false} />);
    expect(screen.getByText("Galletas Casino 43 g")).toBeInTheDocument();
    expect(screen.getByText("Pon un producto dentro del visor: la cámara lo reconoce sola.")).toBeInTheDocument();
    expect(screen.queryByText(/Pasa el siguiente producto/)).not.toBeInTheDocument();
  });
});

describe("PagoQrPropio", () => {
  const paying = { ...base, state: "PAYING", screen: "QR" as const, total_cents: 280 };

  it("muestra el QR del comercio, el monto exacto y el tiempo", () => {
    render(<PagoQrPropio snapshot={paying} offline={false} />);
    expect(screen.getByRole("img", { name: "Código QR de Yape del comercio" })).toHaveAttribute("src", "/api/pay/wallet-qr");
    expect(screen.getByText("S/ 2.80")).toBeInTheDocument();
    expect(screen.getByText("Escanea con Yape o Plin")).toBeInTheDocument();
    expect(screen.getByText("110 s")).toBeInTheDocument();
    expect(screen.getByText("Esperando tu pago. La pantalla avanza sola.")).toBeInTheDocument();
  });

  it("pide escribir el monto exacto, sin cortarlo en dos líneas", () => {
    render(<PagoQrPropio snapshot={paying} offline={false} />);
    // El QR es fijo: el cliente escribe el monto y el pago solo se acepta si coincide.
    const step = screen.getByText(/^Escribe exactamente/);
    expect(step.textContent).toBe("Escribe exactamente S/\u00a02.80");
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
  });

  it("sin imagen configurada lo avisa", () => {
    render(<PagoQrPropio snapshot={{ ...paying, wallet_qr: null }} offline={false} />);
    expect(screen.getByText("Falta el QR del comercio")).toBeInTheDocument();
  });

  it("CANCELAR llama a la API", async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify(paying)));
    vi.stubGlobal("fetch", fetchMock);
    render(<PagoQrPropio snapshot={paying} offline={false} />);
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "CANCELAR COMPRA" })));
    expect(fetchMock).toHaveBeenCalledWith("/api/cancel", expect.objectContaining({ method: "POST" }));
  });
});

describe("Ticket con boleta", () => {
  const paid = {
    ...base,
    state: "PAID",
    screen: "W4" as const,
    seconds_in_state: 2,
    receipt: { number: "B001-00000007", issued_at: "2026-11-20T02:05:00+00:00", payer: "Juan Pérez" },
  };

  it("muestra cobro exitoso, número, fecha y quién pagó", () => {
    render(<Ticket snapshot={paid} />);
    expect(screen.getByText("Cobro exitoso")).toBeInTheDocument();
    expect(screen.getByText("B001-00000007")).toBeInTheDocument();
    expect(screen.getByText("19/11/2026, 21:05")).toBeInTheDocument();
    expect(screen.getByText("Juan Pérez")).toBeInTheDocument();
  });

  it("sin nombre del pagador no muestra esa fila", () => {
    render(<Ticket snapshot={{ ...paid, receipt: { ...paid.receipt, payer: null } }} />);
    expect(screen.queryByText("Cliente")).not.toBeInTheDocument();
  });

  it("es una boleta completa: tienda, productos, cantidades, total y cómo se pagó", () => {
    const snap = {
      ...paid,
      store: "Bodega Don Lucho",
      lines: [{ sku: "A", name: "Glacitas 30 g", quantity: 2, unit_price_cents: 150 }],
      total_cents: 300,
      receipt: { ...paid.receipt, method: "Yape (notificación)", total_cents: 300 },
    };
    render(<Ticket snapshot={snap} />);
    expect(screen.getByText("Bodega Don Lucho")).toBeInTheDocument();
    expect(screen.getByText("Glacitas 30 g")).toBeInTheDocument();
    expect(screen.getByText("S/ 1.50 c/u")).toBeInTheDocument();
    expect(screen.getAllByText("S/ 3.00").length).toBe(2); // importe de la línea y total
    expect(screen.getByText("Yape (notificación)")).toBeInTheDocument();
    expect(screen.getByText(/Boleta simulada, sin validez ante SUNAT/)).toBeInTheDocument();
  });

  it("IMPRIMIR BOLETA abre la impresión y NUEVA COMPRA vuelve al inicio", async () => {
    const print = vi.fn();
    vi.stubGlobal("print", print);
    const fetchMock = vi.fn(async () => new Response(JSON.stringify(paid)));
    vi.stubGlobal("fetch", fetchMock);
    render(<Ticket snapshot={paid} />);
    fireEvent.click(screen.getByRole("button", { name: "IMPRIMIR BOLETA" }));
    expect(print).toHaveBeenCalledOnce();
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "NUEVA COMPRA" })));
    expect(fetchMock).toHaveBeenCalledWith("/api/new-sale", expect.objectContaining({ method: "POST" }));
    expect(screen.getByText("La pantalla vuelve al inicio en 28 s")).toBeInTheDocument();
    vi.unstubAllGlobals();
  });
});
