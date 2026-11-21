import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, request, useKioskState } from "../api";
import { formatDateTime, formatPEN } from "../format";
import { CautionDiamond, StopOctagon } from "../kiosk/signs";
import { PanelHeader } from "./common";
import { SCREEN_NAME } from "./screens";

type HelpRequest = { id: number; screen: keyof typeof SCREEN_NAME; at: number };
type SecurityAlert = {
  id: number;
  reason: string;
  screen: keyof typeof SCREEN_NAME;
  times: number;
  outcome: string;
};

type Sale = {
  number: string;
  issued_at: string;
  items: number;
  total_cents: number;
  lines?: { name: string; quantity: number }[];
  payer?: string | null;
  method?: string;
};
type Sales = { count: number; total_cents: number; receipts: Sale[] };

const SOUND_KEY = "ayuda.sound";
const CAJA_KEY = "ayuda.key"; // clave de caja (solo en la nube; en local no se pide)

function readCajaKey(): string {
  try {
    return localStorage.getItem(CAJA_KEY) ?? "";
  } catch {
    return "";
  }
}

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

/**
 * Vista del encargado (/ayuda): pedidos de SOLICITAR AYUDA, alertas de seguridad (también los
 * Yape que llegan sin compra que calce) con aviso sonoro, y las ventas de hoy con su detalle.
 * Mientras el cliente está en la pantalla de pago aparece «Aprobar pago», para cuando el encargado
 * ve el Yape en su celular pero la notificación no llegó al quiosco. Si el quiosco queda fuera de
 * servicio, aparece arriba con el botón para reactivarlo.
 */
export function AyudaPanel() {
  const { snapshot, connected } = useKioskState();
  const [items, setItems] = useState<HelpRequest[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [now, setNow] = useState(() => Date.now());
  // "at" es el reloj monotónico del servidor: la antigüedad se mide desde que la vemos por primera vez
  const [seen, setSeen] = useState<Record<number, number>>({});
  const [sound, setSound] = useState(readSound);
  const soundRef = useRef(sound);
  const known = useRef(new Set<number>());
  const [alerts, setAlerts] = useState<SecurityAlert[]>([]);
  const knownAlerts = useRef(new Set<number>());
  const cajaKey = useRef(readCajaKey());
  const [needKey, setNeedKey] = useState(false);
  const [keyDraft, setKeyDraft] = useState("");
  const [sales, setSales] = useState<Sales | null>(null);

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

  const fail = useCallback((e: unknown) => {
    if (e instanceof ApiError && e.status === 401) {
      setNeedKey(true); // la nube pide la clave de caja
      setError(null);
      return;
    }
    setError(e instanceof Error ? e.message : "Error desconocido");
  }, []);

  /** Rutas de la caja: llevan la clave guardada (si hay). */
  const caja = useCallback(
    <T,>(method: string, path: string) =>
      request<T>(method, path, undefined, cajaKey.current ? { "X-Caja-Key": cajaKey.current } : {}),
    [],
  );

  const saveKey = (e: React.FormEvent) => {
    e.preventDefault();
    cajaKey.current = keyDraft.trim();
    try {
      localStorage.setItem(CAJA_KEY, cajaKey.current);
    } catch {
      // sin almacenamiento: la clave dura hasta recargar
    }
    setKeyDraft("");
    setNeedKey(false);
  };

  useEffect(() => {
    // Con la pestaña oculta no se consulta (en la nube cada consulta cuenta); al volver, sí.
    const load = () =>
      document.hidden ||
      caja<HelpRequest[]>("GET", "/api/help")
        .then((l) => {
          setError(null);
          setNeedKey(false);
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
  }, [apply, caja, fail]);

  const applyAlerts = useCallback((list: SecurityAlert[]) => {
    let fresh = false;
    for (const a of list) {
      if (!knownAlerts.current.has(a.id)) {
        knownAlerts.current.add(a.id);
        fresh = true;
      }
    }
    if (fresh && soundRef.current) beep();
    setAlerts(list);
  }, []);

  useEffect(() => {
    const load = () =>
      document.hidden ||
      caja<SecurityAlert[]>("GET", "/api/alerts")
        .then(applyAlerts)
        .catch(fail);
    load();
    const poll = setInterval(load, 2000);
    return () => clearInterval(poll);
  }, [applyAlerts, caja, fail]);

  const loadSales = useCallback(
    () =>
      caja<Sales>("GET", "/api/sales")
        .then((s) => setSales(Array.isArray(s?.receipts) ? s : null))
        .catch(fail),
    [caja, fail],
  );

  useEffect(() => {
    const load = () => document.hidden || loadSales();
    load();
    const poll = setInterval(load, 5000);
    return () => clearInterval(poll);
  }, [loadSales]);

  const approve = () =>
    caja("POST", "/api/caja/accept-payment")
      .then(() => {
        setError(null);
        return loadSales();
      })
      .catch(fail);

  const review = (id: number) =>
    caja<SecurityAlert[]>("DELETE", `/api/alerts/${id}`).then(applyAlerts).catch(fail);

  const resolve = (id: number) =>
    caja<HelpRequest[]>("DELETE", `/api/help/${id}`).then(apply).catch(fail);
  const recover = () => caja("POST", "/api/recover").then(() => setError(null)).catch(fail);
  const down = snapshot?.screen === "FUERA_DE_SERVICIO";
  const paying = snapshot?.screen === "QR";

  return (
    <div className="panel">
      <PanelHeader role="Ayuda" connected={connected} />
      {error && <p className="panel-error" role="alert">{error}</p>}
      <div className="ayuda-layout">
        {needKey && (
          <form className="card key-form" onSubmit={saveKey}>
            <h1 className="card-title">Clave de caja</h1>
            <p className="muted">Este quiosco está en internet: escribe la clave para ver las ayudas y alertas.</p>
            <label className="field">
              Clave
              <input
                type="password"
                autoComplete="current-password"
                value={keyDraft}
                onChange={(e) => setKeyDraft(e.target.value)}
                required
              />
            </label>
            <button type="submit" className="pbtn go">Entrar</button>
          </form>
        )}
        {!needKey && down && (
          <section className="card card-down" role="alert">
            <div className="down">
              <StopOctagon className="down-icon" />
              <p>Quiosco 1 fuera de servicio: la cámara dejó de responder. Revisa el equipo y reactívalo.</p>
            </div>
            <button type="button" className="pbtn go" onClick={recover}>
              Reactivar quiosco
            </button>
          </section>
        )}
        {!needKey && paying && snapshot && (
          <section className="card card-paying" aria-label="Cobro en curso">
            <div className="card-head">
              <h2 className="card-title">Cliente pagando {formatPEN(snapshot.total_cents)}</h2>
            </div>
            <p className="muted">
              Si ya ves el Yape por este monto en tu celular y la pantalla no avanza, apruébalo aquí.
            </p>
            <button type="button" className="pbtn go" onClick={approve}>
              Aprobar pago
            </button>
          </section>
        )}
        {!needKey && (
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

          <div className="card-head alerts-head">
            <h2 className="card-title">Alertas de seguridad</h2>
            {alerts.length > 0 && <span className="count">{alerts.length}</span>}
          </div>
          {alerts.length === 0 ? (
            <p className="muted">Sin alertas. Aparece una si algo no se reconoce o si hay un pago que revisar.</p>
          ) : (
            <ul className="requests">
              {alerts.map((a) => (
                <li key={a.id} className="request request-alert">
                  <StopOctagon className="request-icon" />
                  <div className="request-info">
                    <span className="request-title">Quiosco 1<span className="sep">–</span>{a.screen}<span className="sep">–</span>{a.reason}</span>
                    <span className="muted">
                      Alerta #{a.id}<span className="sep">–</span>{a.times === 1 ? "1 vez" : `${a.times} veces`}<span className="sep">–</span>compra {a.outcome}
                    </span>
                  </div>
                  <button type="button" className="pbtn go" onClick={() => review(a.id)}>Revisado</button>
                </li>
              ))}
            </ul>
          )}

          <div className="card-head alerts-head">
            <h2 className="card-title">Ventas de hoy</h2>
            {sales && sales.count > 0 && (
              <span className="muted">
                {sales.count} {sales.count === 1 ? "venta" : "ventas"}<span className="sep">–</span>
                {formatPEN(sales.total_cents)}
              </span>
            )}
          </div>
          {!sales || sales.receipts.length === 0 ? (
            <p className="muted">Sin ventas todavía. Cada venta cobrada aparece aquí con su detalle.</p>
          ) : (
            <ul className="requests">
              {sales.receipts.map((v) => (
                <li key={v.number} className="request sale">
                  <div className="request-info">
                    <span className="request-title">
                      {v.number}<span className="sep">–</span>{formatPEN(v.total_cents)}
                    </span>
                    <span>
                      {(v.lines ?? []).map((l) => `${l.quantity} × ${l.name}`).join(", ") ||
                        `${v.items} ${v.items === 1 ? "producto" : "productos"}`}
                    </span>
                    <span className="muted">
                      {formatDateTime(v.issued_at)}
                      {v.method && (<><span className="sep">–</span>{v.method}</>)}
                      {v.payer && (<><span className="sep">–</span>{v.payer}</>)}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </main>
        )}

      </div>
    </div>
  );
}
