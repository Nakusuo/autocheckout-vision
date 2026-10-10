import { useCallback, useEffect, useState } from "react";
import { request, useKioskState } from "../api";
import { formatPEN } from "../format";
import { CautionDiamond, StopOctagon } from "../kiosk/signs";
import { KioskStatus, PanelHeader } from "./common";
import { SCREEN_NAME } from "./screens";

type HelpRequest = { id: number; screen: keyof typeof SCREEN_NAME; at: number };

export function CajaPanel() {
  const { snapshot, connected } = useKioskState();
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

  const down = snapshot?.screen === "FUERA_DE_SERVICIO";
  const lines = snapshot?.lines ?? [];

  return (
    <div className="panel">
      <PanelHeader role="Caja" connected={connected} />
      {error && <p className="panel-error" role="alert">{error}</p>}
      <div className="caja-layout">
        <main className="card">
          <div className="card-head">
            <h1 className="card-title">Solicitudes de ayuda</h1>
            {items.length > 0 && <span className="count">{items.length}</span>}
          </div>
          {items.length === 0 && (
            <div className="empty-panel">
              <p className="empty-title">Sin solicitudes</p>
              <p className="muted">Cuando un cliente pulse SOLICITAR AYUDA aparecerá aquí.</p>
            </div>
          )}
          <ul className="requests">
            {items.map((r) => (
              <li key={r.id} className="request">
                <CautionDiamond className="request-icon" />
                <div className="request-info">
                  <span className="request-title">Quiosco 1<span className="sep">–</span>{r.screen}<span className="sep">–</span>{SCREEN_NAME[r.screen] ?? r.screen}</span>
                  <span className="muted">
                    Solicitud #{r.id}<span className="sep">–</span>hace {Math.max(0, Math.floor((now - (seen[r.id] ?? now)) / 1000))} s
                  </span>
                </div>
                <button type="button" className="pbtn go" onClick={() => resolve(r.id)}>Atendido</button>
              </li>
            ))}
          </ul>
        </main>

        <aside className="caja-side">
          <section className={`card ${down ? "card-down" : ""}`}>
            <h2 className="card-title">Quiosco 1</h2>
            {down && (
              <div className="down">
                <StopOctagon className="down-icon" />
                <p>La cámara o la balanza dejó de responder. Revisa el equipo y reactívalo.</p>
              </div>
            )}
            <KioskStatus snapshot={snapshot} />
            <button type="button" className={`pbtn ${down ? "go" : "plain"}`} onClick={recover} disabled={!down}>
              Reactivar quiosco
            </button>
          </section>

          <section className="card">
            <h2 className="card-title">Compra en curso</h2>
            {lines.length === 0 ? (
              <p className="muted">No hay productos en la bandeja.</p>
            ) : (
              <div className="sale">
                {lines.map((l) => (
                  <div key={l.sku} className="sale-line">
                    <span>{l.quantity} × {l.name}</span>
                    <span>{formatPEN(l.unit_price_cents * l.quantity)}</span>
                  </div>
                ))}
                <div className="sale-line sale-total">
                  <span>Total</span>
                  <span>{formatPEN(snapshot?.total_cents ?? 0)}</span>
                </div>
              </div>
            )}
          </section>
        </aside>
      </div>
    </div>
  );
}
