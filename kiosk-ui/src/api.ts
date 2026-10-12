import { useEffect, useState } from "react";

export type Snapshot = {
  state: string;
  screen: "W1" | "W2" | "W3" | "QR" | "W4" | "FUERA_DE_SERVICIO";
  can_pay: boolean;
  lines: { sku: string; name: string; quantity: number; unit_price_cents: number }[];
  total_cents: number;
  item_count: number;
  weight: { ok: boolean; diff_g: number } | null;
  /** false sin balanza: solo cuenta lo que reconoce la cámara. */
  weight_enabled: boolean;
  /** true con cámara real: la caja puede recalibrar el fondo (bandeja vacía). */
  camera: boolean;
  alert: string | null;
  seconds_in_state: number;
  help_pending: boolean;
  qr_payload: string | null;
};

const SCREENS = new Set<unknown>(["W1", "W2", "W3", "QR", "W4", "FUERA_DE_SERVICIO"]);

const isObj = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null;
const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const isLine = (v: unknown) =>
  isObj(v) &&
  typeof v.sku === "string" &&
  typeof v.name === "string" &&
  isNum(v.quantity) &&
  isNum(v.unit_price_cents);

/** Comprueba la forma del estado que llega por WebSocket: si no cuadra, la pantalla no lo usa. */
export function isSnapshot(v: unknown): v is Snapshot {
  return (
    isObj(v) &&
    typeof v.state === "string" &&
    SCREENS.has(v.screen) &&
    typeof v.can_pay === "boolean" &&
    Array.isArray(v.lines) &&
    v.lines.every(isLine) &&
    isNum(v.total_cents) &&
    isNum(v.item_count) &&
    (v.weight === null || (isObj(v.weight) && typeof v.weight.ok === "boolean" && isNum(v.weight.diff_g))) &&
    typeof v.weight_enabled === "boolean" &&
    typeof v.camera === "boolean" &&
    (v.alert === null || typeof v.alert === "string") &&
    isNum(v.seconds_in_state) &&
    typeof v.help_pending === "boolean" &&
    (v.qr_payload === null || typeof v.qr_payload === "string")
  );
}

export async function post(path: string, body?: unknown): Promise<Snapshot> {
  return request<Snapshot>("POST", path, body);
}

export async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      method,
      headers: { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new Error("No se pudo conectar. Intente de nuevo");
  }
  if (!res.ok) {
    let detail = `Error ${res.status}`;
    try {
      const data = await res.json();
      if (typeof data?.detail === "string") detail = data.detail;
    } catch {
      /* respuesta sin JSON */
    }
    throw new Error(detail);
  }
  return res.json();
}

export function useKioskState(): { snapshot: Snapshot | null; connected: boolean } {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let closed = false;

    const connect = () => {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      ws = new WebSocket(`${proto}://${location.host}/ws`);
      ws.onopen = () => setConnected(true);
      ws.onmessage = (ev) => {
        let data: unknown;
        try {
          data = JSON.parse(ev.data);
        } catch {
          return; // mensaje malformado: se ignora
        }
        if (isSnapshot(data)) setSnapshot(data);
      };
      ws.onclose = () => {
        if (closed) return;
        setConnected(false);
        timer = setTimeout(connect, 1000);
      };
    };
    connect();

    return () => {
      closed = true;
      clearTimeout(timer);
      ws?.close();
    };
  }, []);

  return { snapshot, connected };
}
