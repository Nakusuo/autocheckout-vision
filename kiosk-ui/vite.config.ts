/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const API = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": API,
      "/sim/": API,
      "/ws": { target: "ws://127.0.0.1:8000", ws: true },
    },
  },
  // Las pruebas e2e usan el build: mismo puerto (kiosk-api solo acepta ese origen) y mismo proxy.
  preview: { port: 5173, strictPort: true },
  // Hilos en vez de procesos: en Windows el primer proceso hijo puede tardar tanto en
  // arrancar que vitest se rinde ("Timeout waiting for worker to respond").
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/setupTests.ts"],
    pool: "threads",
    // .stryker-tmp: copias que deja Stryker (pruebas de mutación)
    exclude: ["**/node_modules/**", "e2e/**", ".stryker-tmp/**"],
  },
});
