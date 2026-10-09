import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, test, type APIRequestContext } from "@playwright/test";

const RECEIPTS = resolve(import.meta.dirname, "..", "..", "kiosk-api", "boletas.jsonl");
const W1_TEXT = "[AUTO-CHECKOUT] Coloca tus productos";

type State = { screen: string; qr_payload: string | null };

async function kioskState(request: APIRequestContext): Promise<State> {
  const res = await request.get("/api/state");
  expect(res.ok()).toBeTruthy();
  return res.json();
}

async function placeOnTray(request: APIRequestContext, skus: string[]) {
  expect((await request.post("/sim/tray", { data: { skus } })).ok()).toBeTruthy();
}

async function setTrap(request: APIRequestContext, offset_g: number) {
  expect((await request.post("/sim/trap", { data: { offset_g } })).ok()).toBeTruthy();
}

function receiptCount(): number {
  try {
    return readFileSync(RECEIPTS, "utf-8").split("\n").filter(Boolean).length;
  } catch {
    return 0;
  }
}

test.beforeEach(async ({ request }) => {
  // Si una venta anterior quedó en W4, el quiosco vuelve solo a W1 a los 10 s.
  await expect
    .poll(async () => (await kioskState(request)).screen, {
      message: "El quiosco debe estar en W1; reinicia kiosk-api si quedó a medias",
      timeout: 15_000,
    })
    .toBe("W1");
  await placeOnTray(request, []);
  await setTrap(request, 0);
});

test("compra de W1 a W4 con trampa de peso, CORREGIR y pago por QR", async ({ page, context, request }) => {
  const receiptsBefore = receiptCount();

  // W1
  await page.goto("/");
  await expect(page.getByText(W1_TEXT)).toBeVisible();
  await page.getByRole("button", { name: "INICIAR" }).click();

  // W2: dos productos reconocidos, pero con peso escondido en la bandeja
  await expect(page.getByRole("heading", { name: "Escaneando" })).toBeVisible();
  await placeOnTray(request, ["AGUA-625", "CHOCOLATE-30"]);
  await setTrap(request, 40);
  await expect(page.getByText("Agua sin gas 625 ml")).toBeVisible();
  await expect(page.getByText("Chocolate de leche 30 g")).toBeVisible();
  await expect(page.getByText("Revise su bandeja")).toBeVisible();
  await expect(page.getByRole("button", { name: "CONFIRMAR" })).toBeDisabled();

  // Se retira el peso escondido: el peso coincide y se puede confirmar
  await setTrap(request, 0);
  await expect(page.getByText("Peso correcto")).toBeVisible();
  await page.getByRole("button", { name: "CONFIRMAR" }).click();

  // W3 → CORREGIR vuelve a W2 → se confirma de nuevo
  await expect(page.getByRole("heading", { name: "Confirma tu compra" })).toBeVisible();
  await page.getByRole("button", { name: "CORREGIR" }).click();
  await expect(page.getByRole("heading", { name: "Escaneando" })).toBeVisible();
  await expect(page.getByText("Peso correcto")).toBeVisible();
  await page.getByRole("button", { name: "CONFIRMAR" }).click();
  await expect(page.getByText("S/ 5.30")).toBeVisible();
  await page.getByRole("button", { name: "PAGAR" }).click();

  // QR dinámico por el monto exacto
  await expect(page.getByRole("img", { name: "Código QR de pago" })).toBeVisible();
  await expect(page.getByText("S/ 5.30")).toBeVisible();
  const { qr_payload } = await kioskState(request);
  expect(qr_payload).toMatch(/^https:\/\/localhost:8443\/pay\//);

  // El "celular" del cliente abre el enlace del QR y paga en la pasarela simulada
  const phone = await context.newPage();
  await phone.goto(qr_payload!);
  await expect(phone.getByText("S/ 5.30")).toBeVisible();
  await phone.getByRole("button", { name: /Pagar con Yape\/Plin/ }).click();
  await expect(phone.getByText("Pago realizado")).toBeVisible();
  await phone.close();

  // W4: ticket tras la confirmación firmada (JWT RS256) y boleta simulada del POS
  await expect(page.getByRole("heading", { name: "Gracias por su compra" })).toBeVisible();
  await expect(page.getByText("S/ 5.30")).toBeVisible();
  expect(receiptCount()).toBe(receiptsBefore + 1);
  const last = JSON.parse(readFileSync(RECEIPTS, "utf-8").trim().split("\n").at(-1)!);
  expect(last.total_cents).toBe(530);

  // A los 10 s vuelve solo a W1 (3.4.4.4)
  await expect(page.getByText(W1_TEXT)).toBeVisible({ timeout: 15_000 });
});

test("SOLICITAR AYUDA llega al panel de caja y se atiende", async ({ page, context }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "SOLICITAR AYUDA" }).click();
  await expect(page.getByText("Ayuda en camino")).toBeVisible();

  const caja = await context.newPage();
  await caja.goto("/caja");
  const item = caja.getByRole("listitem").filter({ hasText: "W1" });
  await expect(item).toBeVisible();
  // Atiende todas las solicitudes pendientes (pueden quedar de corridas anteriores)
  while ((await caja.getByRole("button", { name: "Atendido" }).count()) > 0) {
    await caja.getByRole("button", { name: "Atendido" }).first().click();
  }
  await expect(caja.getByText("Sin solicitudes")).toBeVisible();
  await expect(page.getByText("Ayuda en camino")).toBeHidden();
});
