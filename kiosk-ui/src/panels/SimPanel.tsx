import { useEffect, useState } from "react";
import { request, useKioskState, type Snapshot } from "../api";
import { formatPEN } from "../format";
import { KioskStatus, PanelHeader } from "./common";

type Product = { sku: string; name: string; price_cents: number; weight_g: number };
type Tray = { qty: Record<string, number>; hidden: Record<string, boolean> };

const EMPTY: Tray = { qty: {}, hidden: {} };

/** Acciones del quiosco que el presentador puede disparar desde aquí, según la pantalla. */
const KIOSK_ACTIONS: Partial<Record<Snapshot["screen"], { label: string; path: string }[]>> = {
  W1: [{ label: "Iniciar compra", path: "/api/start" }],
  W2: [
    { label: "Confirmar", path: "/api/confirm" },
    { label: "Volver a escanear", path: "/api/rescan" },
  ],
  W3: [
    { label: "Pagar", path: "/api/pay" },
    { label: "Corregir", path: "/api/correct" },
  ],
  FUERA_DE_SERVICIO: [{ label: "Reactivar quiosco", path: "/api/recover" }],
};

export function SimPanel() {
  const { snapshot, connected } = useKioskState();
  const [catalog, setCatalog] = useState<Product[]>([]);
  const [tray, setTray] = useState<Tray>(EMPTY);
  const [trap, setTrap] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const call = async (method: string, path: string, body?: unknown) => {
    setError(null);
    try {
      await request(method, path, body);
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error desconocido");
      return false;
    }
  };

  useEffect(() => {
    request<Product[]>("GET", "/sim/catalog")
      .then(setCatalog)
      .catch((e) => setError(e instanceof Error ? e.message : "Error desconocido"));
  }, []);

  const place = async (next: Tray) => {
    const skus: string[] = [];
    const hidden: string[] = [];
    for (const p of catalog) {
      const units = Array<string>(next.qty[p.sku] ?? 0).fill(p.sku);
      (next.hidden[p.sku] ? hidden : skus).push(...units);
    }
    if (await call("POST", "/sim/tray", { skus, hidden })) setTray(next);
  };

  const applyTrap = async (grams: number) => {
    if (await call("POST", "/sim/trap", { offset_g: grams })) setTrap(grams);
  };

  const change = (sku: string, delta: number) =>
    place({ ...tray, qty: { ...tray.qty, [sku]: Math.max(0, (tray.qty[sku] ?? 0) + delta) } });
  const toggleHidden = (sku: string) => place({ ...tray, hidden: { ...tray.hidden, [sku]: !tray.hidden[sku] } });

  const [a, b, c, d] = catalog;
  const scenarios: { label: string; detail: string; run: () => void }[] = [
    { label: "Vaciar bandeja", detail: "Sin productos ni peso extra", run: () => { place(EMPTY); applyTrap(0); } },
    ...(a ? [{ label: "Compra de 1", detail: a.name, run: () => place({ qty: { [a.sku]: 1 }, hidden: {} }) }] : []),
    ...(a && b && c
      ? [{ label: "Compra de 3", detail: `${a.name}, ${b.name} y ${c.name}`, run: () => place({ qty: { [a.sku]: 1, [b.sku]: 1, [c.sku]: 1 }, hidden: {} }) }]
      : []),
    ...(a && d
      ? [{ label: "La cámara no ve un producto", detail: `${d.name} pesa pero no se detecta`, run: () => place({ qty: { [a.sku]: 1, [d.sku]: 1 }, hidden: { [d.sku]: true } }) }]
      : []),
    ...(d ? [{ label: "Más de 3 productos", detail: `4 × ${d.name}`, run: () => place({ qty: { [d.sku]: 4 }, hidden: {} }) }] : []),
    { label: "Peso escondido", detail: "+40 g que nadie declaró", run: () => applyTrap(40) },
  ];

  const actions = snapshot ? (KIOSK_ACTIONS[snapshot.screen] ?? []) : [];
  const onTray = Object.values(tray.qty).reduce((n, q) => n + q, 0);

  return (
    <div className="panel">
      <PanelHeader role="Simulador para la presentación" connected={connected} />
      {error && <p className="panel-error" role="alert">{error}</p>}
      <div className="sim-layout">
        <main className="sim-main">
          <section className="card">
            <h2 className="card-title">Escenarios</h2>
            <div className="scenarios">
              {scenarios.map((s) => (
                <button key={s.label} type="button" className="scenario" onClick={s.run}>
                  <span className="scenario-label">{s.label}</span>
                  <span className="scenario-detail">{s.detail}</span>
                </button>
              ))}
            </div>
          </section>

          <section className="card">
            <div className="card-head">
              <h2 className="card-title">Bandeja</h2>
              <span className="muted">{onTray} en la bandeja</span>
            </div>
            <ul className="products">
              {catalog.map((p) => {
                const q = tray.qty[p.sku] ?? 0;
                const hidden = !!tray.hidden[p.sku];
                return (
                  <li key={p.sku} className={`product ${q ? "on" : ""} ${hidden && q ? "hidden" : ""}`}>
                    <div className="product-info">
                      <span className="product-name">{p.name}</span>
                      <span className="muted">{formatPEN(p.price_cents)}<span className="sep">–</span>{p.weight_g} g</span>
                    </div>
                    <div className="stepper">
                      <button type="button" aria-label={`Quitar ${p.name}`} disabled={q === 0} onClick={() => change(p.sku, -1)}>−</button>
                      <span aria-label={`Cantidad de ${p.name}`}>{q}</span>
                      <button type="button" aria-label={`Añadir ${p.name}`} onClick={() => change(p.sku, 1)}>+</button>
                    </div>
                    <label className="hide-toggle">
                      <input type="checkbox" checked={hidden} onChange={() => toggleHidden(p.sku)} />
                      La cámara no lo ve
                    </label>
                  </li>
                );
              })}
            </ul>
          </section>

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
