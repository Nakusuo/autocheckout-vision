import { existsSync } from "node:fs";
import { join, resolve } from "node:path";
import { defineConfig, devices } from "@playwright/test";

// Pruebas de punta a punta (W1 a W4) con los servicios reales en modo simulado:
// mock-gateway (HTTPS, TLS 1.3), kiosk-api (KIOSK_MODE=sim) y la UI de Vite.

const REPO = resolve(import.meta.dirname, "..");
const API_KEY = process.env.GATEWAY_API_KEY ?? "clave-solo-para-pruebas-e2e";

// Usa el .venv de cada servicio si existe (desarrollo); si no, el `python` del PATH (CI).
function python(service: string): string {
  const venv = process.platform === "win32"
    ? join(REPO, service, ".venv", "Scripts", "python.exe")
    : join(REPO, service, ".venv", "bin", "python");
  return existsSync(venv) ? `"${venv}"` : "python";
}

const env = { GATEWAY_API_KEY: API_KEY, KIOSK_MODE: "sim", PYTHONUTF8: "1" };

export default defineConfig({
  testDir: "./e2e",
  testMatch: "**/*.e2e.ts",
  // Un solo quiosco compartido: las pruebas van en serie.
  workers: 1,
  fullyParallel: false,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: "http://localhost:5173",
    ...devices["Desktop Chrome"],
    viewport: { width: 1080, height: 1920 },
    ignoreHTTPSErrors: true, // certificado de desarrollo de mock-gateway
    trace: "retain-on-failure",
  },
  webServer: [
    {
      // devkeys no pisa claves existentes: es seguro ejecutarlo siempre.
      command: `${python("mock-gateway")} -m gateway.devkeys && ${python("mock-gateway")} -m gateway`,
      cwd: join(REPO, "mock-gateway"),
      url: "https://localhost:8443/docs",
      ignoreHTTPSErrors: true,
      env,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
    {
      command: `${python("kiosk-api")} -m kiosk`,
      cwd: join(REPO, "kiosk-api"),
      url: "http://127.0.0.1:8000/api/state",
      env,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
    {
      // El build y no `vite dev`: en frío, Vite optimiza dependencias y recarga la página a mitad de la prueba.
      command: "npm run build && npm run preview",
      url: "http://localhost:5173",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
});
