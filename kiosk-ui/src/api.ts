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
        try {
          setSnapshot(JSON.parse(ev.data) as Snapshot);
        } catch {
          /* mensaje malformado: se ignora */
        }
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
