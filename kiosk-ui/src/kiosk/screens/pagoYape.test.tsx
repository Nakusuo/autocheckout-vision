import { act, fireEvent, render, screen } from "@testing-library/react";
import type { Snapshot } from "../../api";
import { PagoYape } from "./PagoYape";

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
  qr_payload: null,
  payment_method: "yape",
  payment_error: null,
  payment_processing: false,
};

afterEach(() => vi.unstubAllGlobals());

const key = (name: string) => screen.getByRole("button", { name });
const type = (digits: string) => {
  for (const d of digits) fireEvent.click(key(d));
};
const pay = () => screen.getByRole("button", { name: "PAGAR CON YAPE" });
const phone = () => screen.getByTestId("yape-phone");
const otp = () => screen.getByTestId("yape-otp");

it("muestra total, pista del código y segundos restantes", () => {
  render(<PagoYape snapshot={snap} offline={false} />);
  expect(screen.getByText("Total a pagar con Yape")).toBeInTheDocument();
  expect(screen.getByText("S/ 5.30")).toBeInTheDocument();
  expect(screen.getByText(/Código de aprobación» \(dura 2 min\)/)).toBeInTheDocument();
  expect(screen.getByLabelText("Quedan 110 segundos para pagar")).toHaveTextContent("110 s");
  expect(phone()).toHaveTextContent("9 dígitos");
  expect(otp()).toHaveTextContent("6 dígitos");
  expect(pay()).toBeDisabled();
});

it("el teclado escribe el celular agrupado y pasa solo al código", () => {
  render(<PagoYape snapshot={snap} offline={false} />);
  type("987654321");
  expect(phone()).toHaveTextContent("987 654 321");
  expect(screen.getByRole("group", { name: "Teclado: código" })).toBeInTheDocument();
  type("123456");
  expect(otp()).toHaveTextContent("123456");
  expect(pay()).toBeEnabled();
});

it("no acepta más dígitos de la cuenta", () => {
  render(<PagoYape snapshot={snap} offline={false} />);
  type("987654321");
  fireEvent.click(screen.getByRole("button", { name: /Celular/ }));
  type("0");
  expect(phone()).toHaveTextContent("987 654 321");
  fireEvent.click(screen.getByRole("button", { name: /Código de aprobación/ }));
  type("1234567");
  expect(otp()).toHaveTextContent("123456");
});

it("borrar quita un dígito y Borrar todo vacía el campo activo", () => {
  render(<PagoYape snapshot={snap} offline={false} />);
  type("987");
  fireEvent.click(key("Borrar un dígito"));
  expect(phone()).toHaveTextContent("98");
  fireEvent.click(key("Borrar todo"));
  expect(phone()).toHaveTextContent("9 dígitos");
});

it("se puede volver al campo del celular para corregirlo", () => {
  render(<PagoYape snapshot={snap} offline={false} />);
  type("987654321");
  fireEvent.click(screen.getByRole("button", { name: /Celular/ }));
  expect(screen.getByRole("button", { name: /Celular/ })).toHaveAttribute("aria-pressed", "true");
  fireEvent.click(key("Borrar un dígito"));
  expect(phone()).toHaveTextContent("987 654 32");
  fireEvent.click(screen.getByRole("button", { name: /Código de aprobación/ }));
  type("1");
  expect(otp()).toHaveTextContent("1");
});

it("PAGAR envía celular y código a /api/pay/yape", async () => {
  const fetchMock = vi.fn(async () => new Response(JSON.stringify(snap)));
  vi.stubGlobal("fetch", fetchMock);
  render(<PagoYape snapshot={snap} offline={false} />);
  type("111111111");
  type("123456");
  await act(async () => fireEvent.click(pay()));
  expect(fetchMock).toHaveBeenCalledWith("/api/pay/yape", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ phone: "111111111", otp: "123456" }),
  });
});

it("mientras procesa: aviso y todo deshabilitado (también CANCELAR)", () => {
  render(<PagoYape snapshot={{ ...snap, payment_processing: true }} offline={false} />);
  expect(screen.getByRole("status")).toHaveTextContent("Procesando pago con Yape…");
  expect(key("1")).toBeDisabled();
  expect(pay()).toBeDisabled();
  expect(screen.getByRole("button", { name: "CANCELAR COMPRA" })).toBeDisabled();
});

it("al pagar se borra el código usado; un rechazo se muestra", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(snap))));
  const { rerender } = render(<PagoYape snapshot={snap} offline={false} />);
  type("111111117");
  type("123456");
  await act(async () => fireEvent.click(pay()));
  rerender(
    <PagoYape snapshot={{ ...snap, payment_error: "Código de aprobación incorrecto o vencido" }} offline={false} />,
  );
  expect(screen.getByRole("alert")).toHaveTextContent("Código de aprobación incorrecto o vencido");
  expect(otp()).toHaveTextContent("6 dígitos");
  expect(phone()).toHaveTextContent("111 111 117");
  expect(pay()).toBeDisabled();
});

it("sin conexión no deja pagar", () => {
  render(<PagoYape snapshot={snap} offline />);
  type("111111111");
  type("123456");
  expect(pay()).toBeDisabled();
});

it("un error de la API se muestra", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ detail: "No hay un cobro en curso" }), { status: 409 })));
  render(<PagoYape snapshot={snap} offline={false} />);
  type("111111111");
  type("123456");
  await act(async () => fireEvent.click(pay()));
  expect(screen.getByRole("alert")).toHaveTextContent("No hay un cobro en curso");
});
