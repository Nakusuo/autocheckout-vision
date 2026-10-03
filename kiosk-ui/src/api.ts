import { useEffect, useState } from "react";

export type Snapshot = {
  state: string;
  screen: "W1" | "W2" | "W3" | "QR" | "W4" | "FUERA_DE_SERVICIO";
  can_pay: boolean;
  lines: { sku: string; name: string; quantity: number; unit_price_cents: number }[];
  total_cents: number;
  item_count: number;
  weight: { ok: boolean; diff_g: number } | null;
  alert: string | null;
  seconds_in_state: number;
  help_pending: boolean;
};

export async function post(path: string, body?: unknown): Promise<Snapshot> {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
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

export function useKioskState(): Snapshot | null {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);

  useEffect(() => {
    let ws: WebSocket | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let closed = false;

    const connect = () => {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      ws = new WebSocket(`${proto}://${location.host}/ws`);
      ws.onmessage = (ev) => setSnapshot(JSON.parse(ev.data) as Snapshot);
      ws.onclose = () => {
        if (!closed) timer = setTimeout(connect, 1000);
      };
    };
    connect();

    return () => {
      closed = true;
      clearTimeout(timer);
      ws?.close();
    };
  }, []);

  return snapshot;
}
