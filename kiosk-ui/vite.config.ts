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
  test: { environment: "jsdom", globals: true, setupFiles: ["./src/setupTests.ts"] },
});
