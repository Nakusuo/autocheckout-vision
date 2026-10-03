import { useCallback, useEffect, useState } from "react";
import { request } from "../api";

type HelpRequest = { id: number; screen: string; at: number };

export function CajaPanel() {
  const [items, setItems] = useState<HelpRequest[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [now, setNow] = useState(() => Date.now());
  // "at" es el reloj monotónico del servidor: la antigüedad se mide desde que la vemos por primera vez
  const [seen, setSeen] = useState<Record<number, number>>({});

  const apply = useCallback((list: HelpRequest[]) => {
    const t = Date.now();
    setSeen((prev) => {
      const next = { ...prev };
      for (const r of list) if (!(r.id in next)) next[r.id] = t;
      return next;
    });
    setItems(list);
  }, []);

  const fail = (e: unknown) => setError(e instanceof Error ? e.message : "Error desconocido");

  useEffect(() => {
    const load = () =>
      request<HelpRequest[]>("GET", "/api/help")
        .then((l) => {
          setError(null);
          apply(l);
        })
        .catch(fail);
    load();
    const poll = setInterval(load, 2000);
    const tick = setInterval(() => setNow(Date.now()), 1000);
    return () => {
      clearInterval(poll);
      clearInterval(tick);
    };
  }, [apply]);

  const resolve = (id: number) =>
    request<HelpRequest[]>("DELETE", `/api/help/${id}`).then(apply).catch(fail);
  const recover = () => request("POST", "/api/recover").then(() => setError(null)).catch(fail);

  return (
    <main style={{ padding: 16, fontFamily: "system-ui, sans-serif", maxWidth: 640 }}>
      <h1>Caja</h1>
      {error && <p role="alert" style={{ color: "#c62828" }}>{error}</p>}
      <h2>Solicitudes de ayuda</h2>
      {items.length === 0 && <p>Sin solicitudes</p>}
      <ul style={{ listStyle: "none", padding: 0 }}>
        {items.map((r) => (
          <li key={r.id} style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 8 }}>
            <span style={{ flex: 1 }}>
              #{r.id} - {r.screen} - hace {Math.max(0, Math.floor((now - (seen[r.id] ?? now)) / 1000))} s
            </span>
            <button type="button" onClick={() => resolve(r.id)}>Atendido</button>
          </li>
        ))}
      </ul>
      <button type="button" onClick={recover}>Reactivar quiosco</button>
    </main>
  );
}
