import { isSnapshot, type Snapshot } from "./api";

const ok: Snapshot = {
  state: "SCANNING",
  screen: "W2",
  can_pay: false,
  lines: [{ sku: "AGUA", name: "Agua", quantity: 1, unit_price_cents: 250 }],
  total_cents: 250,
  item_count: 1,
  weight: { ok: true, diff_g: 0 },
  weight_enabled: true,
  camera: false,
  alert: null,
  seconds_in_state: 1.5,
  help_pending: false,
  qr_payload: null,
};

it("acepta un estado válido, también con nulos y textos", () => {
  expect(isSnapshot(ok)).toBe(true);
  expect(isSnapshot({ ...ok, weight: null, alert: "Revise su bandeja", qr_payload: "https://x/pay/1" })).toBe(true);
});

it.each([
  ["no es objeto", null],
  ["pantalla desconocida", { ...ok, screen: "W9" }],
  ["state no es texto", { ...ok, state: 1 }],
  ["can_pay no es booleano", { ...ok, can_pay: "no" }],
  ["lines no es lista", { ...ok, lines: {} }],
  ["línea sin nombre", { ...ok, lines: [{ sku: "A", quantity: 1, unit_price_cents: 1 }] }],
  ["línea con sku numérico", { ...ok, lines: [{ ...ok.lines[0], sku: 1 }] }],
  ["cantidad no numérica", { ...ok, lines: [{ ...ok.lines[0], quantity: "1" }] }],
  ["precio infinito", { ...ok, lines: [{ ...ok.lines[0], unit_price_cents: Infinity }] }],
  ["línea nula", { ...ok, lines: [null] }],
  ["total NaN", { ...ok, total_cents: NaN }],
  ["item_count texto", { ...ok, item_count: "1" }],
  ["peso sin ok", { ...ok, weight: { diff_g: 0 } }],
  ["peso con diff texto", { ...ok, weight: { ok: true, diff_g: "0" } }],
  ["weight_enabled ausente", { ...ok, weight_enabled: undefined }],
  ["camera texto", { ...ok, camera: "true" }],
  ["alerta numérica", { ...ok, alert: 3 }],
  ["segundos texto", { ...ok, seconds_in_state: "1" }],
  ["help_pending nulo", { ...ok, help_pending: null }],
  ["qr numérico", { ...ok, qr_payload: 5 }],
])("rechaza: %s", (_, value) => {
  expect(isSnapshot(value)).toBe(false);
});
