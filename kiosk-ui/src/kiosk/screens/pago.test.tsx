import { act, fireEvent, render, screen } from "@testing-library/react";
import QRCode from "qrcode";
import type { Snapshot } from "../../api";
import { Pago } from "./Pago";

// QR controlado a mano: cada llamada queda pendiente hasta que la prueba la resuelva.
vi.mock("qrcode", () => ({ default: { toDataURL: vi.fn() } }));
const toDataURL = vi.mocked(QRCode.toDataURL) as unknown as ReturnType<typeof vi.fn>;

type Deferred = { resolve: (url: string) => void; reject: (e: Error) => void };
let calls: Deferred[];

beforeEach(() => {
  calls = [];
  toDataURL.mockReset();
  toDataURL.mockImplementation(
    () => new Promise<string>((resolve, reject) => calls.push({ resolve, reject })),
  );
});
afterEach(() => vi.unstubAllGlobals());

const snap: Snapshot = {
  state: "PAYING",
  screen: "QR",
  can_pay: false,
  lines: [],
  total_cents: 530,
  item_count: 2,
  weight: null,
  weight_enabled: false,
  camera: false,
  alert: null,
  seconds_in_state: 10,
  help_pending: false,
  qr_payload: "https://localhost:8443/pay/ch_1",
};

const pending = () => screen.queryByText("Generando código QR…");
const img = () => screen.queryByRole("img", { name: "Código QR de pago" });

it("muestra total, pista y segundos restantes", () => {
  render(<Pago snapshot={snap} offline={false} />);
  expect(screen.getByText("Total a pagar")).toBeInTheDocument();
  expect(screen.getByText("S/ 5.30")).toBeInTheDocument();
  expect(screen.getByText("Escanea con Yape o Plin")).toBeInTheDocument();
  expect(screen.getByText("110 s")).toBeInTheDocument();
  expect(screen.getByText("Esperando confirmación del pago")).toBeInTheDocument();
});

it("genera el QR con las opciones de impresión del quiosco", async () => {
  render(<Pago snapshot={snap} offline={false} />);
  expect(toDataURL).toHaveBeenCalledTimes(1);
  expect(toDataURL).toHaveBeenCalledWith(snap.qr_payload, {
    margin: 1,
    width: 640,
    errorCorrectionLevel: "M",
    color: { dark: "#141414", light: "#ffffff" },
  });
  expect(pending()).toBeInTheDocument();
  await act(async () => calls[0].resolve("data:image/png;base64,AAA"));
  expect(img()).toHaveAttribute("src", "data:image/png;base64,AAA");
  expect(pending()).not.toBeInTheDocument();
});

it("sin enlace de pago no genera nada", () => {
  render(<Pago snapshot={{ ...snap, qr_payload: null }} offline={false} />);
  expect(toDataURL).not.toHaveBeenCalled();
  expect(pending()).toBeInTheDocument();
});

it("si el QR falla, sigue mostrando «Generando…»", async () => {
  render(<Pago snapshot={snap} offline={false} />);
  await act(async () => calls[0].reject(new Error("x")));
  expect(img()).not.toBeInTheDocument();
  expect(pending()).toBeInTheDocument();
});

it("un fallo del QR nuevo borra el anterior", async () => {
  const { rerender } = render(<Pago snapshot={snap} offline={false} />);
  await act(async () => calls[0].resolve("data:A"));
  rerender(<Pago snapshot={{ ...snap, qr_payload: "https://localhost:8443/pay/ch_2" }} offline={false} />);
  await act(async () => calls[1].reject(new Error("x")));
  rerender(<Pago snapshot={snap} offline={false} />);
  // vuelve al enlace 1: como el último resultado fue un fallo, no hay QR guardado
  expect(img()).not.toBeInTheDocument();
});

it("ignora un QR que llega tarde para un enlace viejo", async () => {
  const { rerender } = render(<Pago snapshot={snap} offline={false} />);
  rerender(<Pago snapshot={{ ...snap, qr_payload: "https://localhost:8443/pay/ch_2" }} offline={false} />);
  await act(async () => calls[1].resolve("data:NUEVO"));
  await act(async () => calls[0].resolve("data:VIEJO"));
  expect(img()).toHaveAttribute("src", "data:NUEVO");
});

it("ignora un fallo que llega tarde para un enlace viejo", async () => {
  const { rerender } = render(<Pago snapshot={snap} offline={false} />);
  rerender(<Pago snapshot={{ ...snap, qr_payload: "https://localhost:8443/pay/ch_2" }} offline={false} />);
  await act(async () => calls[1].resolve("data:NUEVO"));
  await act(async () => calls[0].reject(new Error("x")));
  expect(img()).toHaveAttribute("src", "data:NUEVO");
});

it("CANCELAR se deshabilita mientras se envía", async () => {
  let finish!: (r: Response) => void;
  vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>((r) => (finish = r))));
  render(<Pago snapshot={snap} offline={false} />);
  const cancel = screen.getByRole("button", { name: "CANCELAR COMPRA" });
  expect(cancel).toBeEnabled();
  await act(async () => fireEvent.click(cancel));
  expect(cancel).toBeDisabled();
  await act(async () => finish(new Response(JSON.stringify(snap))));
  expect(cancel).toBeEnabled();
});
