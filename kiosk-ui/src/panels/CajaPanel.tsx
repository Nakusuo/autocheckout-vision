import { useCallback, useEffect, useRef, useState } from "react";
import { request, useKioskState } from "../api";
import { formatPEN } from "../format";
import { CautionDiamond, StopOctagon } from "../kiosk/signs";
import { KioskStatus, PanelHeader } from "./common";
import { SCREEN_NAME } from "./screens";

type HelpRequest = { id: number; screen: keyof typeof SCREEN_NAME; at: number };
type Receipt = { number: string; issued_at: string; items: number; total_cents: number };
type Sales = { count: number; total_cents: number; receipts: Receipt[] };

const SOUND_KEY = "caja.sound";

function readSound(): boolean {
  try {
    return localStorage.getItem(SOUND_KEY) !== "off";
  } catch {
    return true;
  }
}

/** Dos pitidos cortos a 880 Hz. Sin Web Audio (o bloqueado por autoplay) no hace nada. */
function beep() {
  try {
    const Ctx = window.AudioContext;
    if (!Ctx) return;
    const ctx = new Ctx();
    for (const start of [0, 0.3]) {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.value = 880;
      gain.gain.value = 0.2;
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(ctx.currentTime + start);
      osc.stop(ctx.currentTime + start + 0.2);
    }
    setTimeout(() => void ctx.close().catch(() => undefined), 1000);
  } catch {
    // sin audio: la lista sigue avisando visualmente
  }
}

const hhmm = (iso: string) => {
  const d = new Date(iso);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
};

export function CajaPanel() {
  const { snapshot, connected } = useKioskState();
  const [items, setItems] = useState<HelpRequest[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [now, setNow] = useState(() => Date.now());
  // "at" es el reloj monotónico del servidor: la antigüedad se mide desde que la vemos por primera vez
  const [seen, setSeen] = useState<Record<number, number>>({});
  const [sales, setSales] = useState<Sales | null>(null);
  const [sound, setSound] = useState(readSound);
  const soundRef = useRef(sound);
  const known = useRef(new Set<number>());

  const toggleSound = () => {
    const next = !sound;
    setSound(next);
    soundRef.current = next;
    try {
      localStorage.setItem(SOUND_KEY, next ? "on" : "off");
    } catch {
      // sin almacenamiento: la preferencia dura hasta recargar
    }
  };

  const apply = useCallback((list: HelpRequest[]) => {
    const t = Date.now();
    let fresh = false;
    for (const r of list) {
      if (!known.current.has(r.id)) {
        known.current.add(r.id);
        fresh = true;
      }
    }
    if (fresh && soundRef.current) beep();
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

  useEffect(() => {
    const load = () =>
      request<Sales>("GET", "/api/sales")
        .then(setSales)
        .catch(fail);
    load();
    const poll = setInterval(load, 5000);
    return () => clearInterval(poll);
  }, []);

  const resolve = (id: number) =>
    request<HelpRequest[]>("DELETE", `/api/help/${id}`).then(apply).catch(fail);
  const recover = () => request("POST", "/api/recover").then(() => setError(null)).catch(fail);
  const [calibrating, setCalibrating] = useState(false);
  const recalibrate = () =>
    request("POST", "/api/recalibrate")
      .then(() => {
        setError(null);
        setCalibrating(true);
        setTimeout(() => setCalibrating(false), 4000);
      })
      .catch(fail);

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
            <span className="card-head-tools">
              {items.length > 0 && <span className="count">{items.length}</span>}
              <button type="button" className="pbtn plain sound-toggle" aria-pressed={sound} onClick={toggleSound}>
                Sonido: {sound ? "sí" : "no"}
              </button>
            </span>
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
            {snapshot?.camera && (
              <>
                <button type="button" className="pbtn plain" onClick={recalibrate} disabled={calibrating}>
                  {calibrating ? "Calibrando…" : "Recalibrar cámara"}
                </button>
                <p className="muted">
                  {calibrating
                    ? "Deja la bandeja vacía unos segundos."
                    : "Úsalo si la cámara se movió o había algo en la bandeja al encenderla."}
                </p>
              </>
            )}
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

          <section className="card">
            <h2 className="card-title">Ventas de hoy</h2>
            {!sales || sales.count === 0 ? (
              <p className="muted">Aún no hay ventas hoy.</p>
            ) : (
              <div className="sale">
                <div className="sale-line sale-total">
                  <span>{sales.count} {sales.count === 1 ? "venta" : "ventas"}</span>
                  <span>{formatPEN(sales.total_cents)}</span>
                </div>
                {sales.receipts.map((r) => (
                  <div key={r.number} className="sale-line receipt-line">
                    <span>
                      {hhmm(r.issued_at)}<span className="sep">–</span>{r.number}<span className="sep">–</span>
                      {r.items} {r.items === 1 ? "producto" : "productos"}
                    </span>
                    <span>{formatPEN(r.total_cents)}</span>
                  </div>
                ))}
              </div>
            )}
          </section>
        </aside>
      </div>
    </div>
  );
}
