import { useCallback, useEffect, useRef, useState } from "react";
import { request, useKioskState, type Snapshot } from "../api";
import { formatPEN } from "../format";
import { KioskStatus, PanelHeader } from "./common";

type Product = { sku: string; name: string; price_cents: number; weight_g: number };
type TrayState = { tray: string[]; camera: string[] };
type Step = { kind: "scan" | "sneak" | "trap" | "empty"; sku?: string; grams?: number };

const STEP_GAP_MS = 1800; // pausa entre productos en los escenarios, para que se vea cada uno

/** Acciones del quiosco que el presentador puede disparar desde aquí, según la pantalla. */
const KIOSK_ACTIONS: Partial<Record<Snapshot["screen"], { label: string; path: string }[]>> = {
  W1: [{ label: "Iniciar compra", path: "/api/start" }],
  W2: [
    { label: "Confirmar", path: "/api/confirm" },
    { label: "Cancelar compra", path: "/api/cancel" },
  ],
  W3: [
    { label: "Pagar", path: "/api/pay" },
    { label: "Corregir", path: "/api/correct" },
    { label: "Cancelar compra", path: "/api/cancel" },
  ],
  QR: [{ label: "Cancelar compra", path: "/api/cancel" }],
  FUERA_DE_SERVICIO: [{ label: "Reactivar quiosco", path: "/api/recover" }],
};

const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));

export function SimPanel() {
  const { snapshot, connected } = useKioskState();
  const [catalog, setCatalog] = useState<Product[]>([]);
  const [tray, setTray] = useState<string[]>([]);
  const [camera, setCamera] = useState<string[]>([]);
  const [trap, setTrap] = useState(0);
  const [running, setRunning] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const unmounted = useRef(false);

  const call = useCallback(async <T,>(method: string, path: string, body?: unknown): Promise<T | null> => {
    setError(null);
    try {
      return await request<T>(method, path, body);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error desconocido");
      return null;
    }
  }, []);

  useEffect(() => {
    unmounted.current = false;
    const refreshTray = () =>
      request<TrayState>("GET", "/sim/tray")
        .then((r) => {
          setTray(r.tray);
          setCamera(r.camera);
        })
        .catch(() => undefined);
    request<Product[]>("GET", "/sim/catalog")
      .then(setCatalog)
      .catch((e) => setError(e instanceof Error ? e.message : "Error desconocido"));
    refreshTray();
    const poll = setInterval(refreshTray, 500);
    return () => {
      unmounted.current = true;
      clearInterval(poll);
    };
  }, []);

  const onTray = async (path: string, sku: string) => {
    const r = await call<TrayState>("POST", path, { sku });
    if (r) {
      setTray(r.tray);
      setCamera(r.camera);
    }
  };
  const applyTrap = async (grams: number) => {
    if ((await call("POST", "/sim/trap", { offset_g: grams })) !== null) setTrap(grams);
  };
  const emptyTray = async () => {
    if ((await call("POST", "/sim/tray", { skus: [] })) !== null) {
      setTray([]);
      setCamera([]);
    }
  };

  const runSteps = async (label: string, steps: Step[]) => {
    setRunning(label);
    for (const [i, step] of steps.entries()) {
      if (unmounted.current) break;
      if (i > 0) await wait(STEP_GAP_MS);
      if (step.kind === "scan" && step.sku) await onTray("/sim/scan", step.sku);
      if (step.kind === "sneak" && step.sku) await onTray("/sim/sneak", step.sku);
      if (step.kind === "trap") await applyTrap(step.grams ?? 0);
      if (step.kind === "empty") {
        await emptyTray();
        await applyTrap(0);
      }
    }
    setRunning(null);
  };

  const scan = (sku: string): Step => ({ kind: "scan", sku });
  const scaleOn = snapshot?.weight_enabled ?? false;
  const [a, b, c, d] = catalog;
  const scenarios: { label: string; detail: string; steps: Step[] }[] = [
    { label: "Vaciar bandeja", detail: "Sin productos ni peso extra", steps: [{ kind: "empty" }] },
    ...(a && b && c
      ? [{ label: "Compra de 3, uno por uno", detail: `${a.name}, ${b.name} y ${c.name}`, steps: [scan(a.sku), scan(b.sku), scan(c.sku)] }]
      : []),
    ...(d ? [{ label: "El mismo producto dos veces", detail: `2 × ${d.name}`, steps: [scan(d.sku), scan(d.sku)] }] : []),
    // Sin balanza no hay forma de notar un producto sin escanear: esos escenarios se ocultan.
    ...(scaleOn && a && d
      ? [{ label: "La cámara no ve un producto", detail: `${d.name} va a la bandeja sin escanear`, steps: [scan(a.sku), { kind: "sneak" as const, sku: d.sku }] }]
      : []),
    ...(d ? [{ label: "Más de 3 productos", detail: `4 × ${d.name}, uno por uno`, steps: [scan(d.sku), scan(d.sku), scan(d.sku), scan(d.sku)] }] : []),
    ...(scaleOn ? [{ label: "Peso escondido", detail: "+40 g que nadie declaró", steps: [{ kind: "trap" as const, grams: 40 }] }] : []),
  ];

  const actions = snapshot ? (KIOSK_ACTIONS[snapshot.screen] ?? []) : [];
  const count = (sku: string) => tray.filter((s) => s === sku).length;

  return (
    <div className="panel">
      <PanelHeader role="Simulador para la presentación" connected={connected} />
      {error && <p className="panel-error" role="alert">{error}</p>}
      <div className="sim-layout">
        <main className="sim-main">
          <section className="card">
            <div className="card-head">
              <h2 className="card-title">Escenarios</h2>
              {running && <span className="running">Ejecutando: {running}…</span>}
            </div>
            <div className="scenarios">
              {scenarios.map((s) => (
                <button key={s.label} type="button" className="scenario" disabled={running !== null} onClick={() => runSteps(s.label, s.steps)}>
                  <span className="scenario-label">{s.label}</span>
                  <span className="scenario-detail">{s.detail}</span>
                </button>
              ))}
            </div>
          </section>

          <section className="card">
            <div className="card-head">
              <h2 className="card-title">Productos</h2>
              <span className="muted">{tray.length} en la bandeja</span>
            </div>
            <p className="muted">Pasa cada producto por la cámara, como haría el cliente. Después queda en la bandeja.</p>
            <ul className="products">
              {catalog.map((p) => {
                const n = count(p.sku);
                const seen = camera.includes(p.sku);
                return (
                  <li key={p.sku} className={`product ${n ? "on" : ""} ${seen ? "seen" : ""}`}>
                    <div className="product-info">
                      <span className="product-name">
                        {p.name}
                        {seen && <span className="seen-tag">Frente a la cámara</span>}
                      </span>
                      <span className="muted">{formatPEN(p.price_cents)}<span className="sep">–</span>{p.weight_g} g</span>
                    </div>
                    <span className="product-count" aria-label={`En la bandeja: ${p.name}`}>{n}</span>
                    <div className="product-actions">
                      <button type="button" className="pbtn go" disabled={running !== null} onClick={() => onTray("/sim/scan", p.sku)}>
                        Pasar por la cámara
                      </button>
                      {scaleOn && (
                        <button type="button" className="pbtn plain" disabled={running !== null} onClick={() => onTray("/sim/sneak", p.sku)}>
                          Sin escanear
                        </button>
                      )}
                      <button type="button" className="pbtn plain" disabled={running !== null || n === 0} onClick={() => onTray("/sim/take", p.sku)}>
                        Sacar
                      </button>
                    </div>
                  </li>
                );
              })}
            </ul>
          </section>

          {scaleOn ? (
          <section className="card">
            <h2 className="card-title">Balanza</h2>
            <p className="muted">Peso extra que la cámara no ve (por ejemplo, un producto escondido).</p>
            <div className="trap">
              {[0, 20, 40, -20].map((g) => (
                <button key={g} type="button" className={`chip ${trap === g ? "active" : ""}`} onClick={() => applyTrap(g)}>
                  {g === 0 ? "Sin trampa" : `${g > 0 ? "+" : ""}${g} g`}
                </button>
              ))}
            </div>
          </section>
          ) : (
            <section className="card">
              <h2 className="card-title">Balanza</h2>
              <p className="muted">Sin balanza (KIOSK_SCALE=off): el quiosco cobra lo que reconoce la cámara.</p>
            </section>
          )}
        </main>

        <aside className="sim-side">
          <section className="card">
            <h2 className="card-title">Quiosco ahora</h2>
            <KioskStatus snapshot={snapshot} />
            {actions.length > 0 && (
              <div className="remote">
                {actions.map((act, i) => (
                  <button key={act.path} type="button" className={`pbtn ${i === 0 ? "go" : "plain"}`} onClick={() => call("POST", act.path)}>
                    {act.label}
                  </button>
                ))}
              </div>
            )}
          </section>

          <section className="card">
            <h2 className="card-title">Pago</h2>
            {snapshot?.screen === "QR" && snapshot.qr_payload ? (
              <>
                <a className="pbtn go" href={snapshot.qr_payload} target="_blank" rel="noopener noreferrer">
                  Abrir el celular simulado
                </a>
                <p className="muted">Paga ahí con «Pagar con Yape/Plin». La primera vez acepta el certificado de desarrollo.</p>
              </>
            ) : (
              <p className="muted">El enlace de pago aparece cuando el quiosco muestra el QR.</p>
            )}
          </section>

          <section className="card preview">
            <h2 className="card-title">Vista del cliente</h2>
            <iframe className="preview-frame" src="/" title="Vista del quiosco" />
          </section>
        </aside>
      </div>
    </div>
  );
}
