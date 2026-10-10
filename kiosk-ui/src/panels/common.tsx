import "./panels.css";
import type { Snapshot } from "../api";
import { SCREEN_NAME } from "./screens";


export function PanelHeader({ role, connected }: { role: string; connected: boolean }) {
  return (
    <header className="panel-header">
      <span className="wordmark">Auto<span>Caja</span></span>
      <span className="panel-role">{role}</span>
      <span className={`link-state ${connected ? "on" : "off"}`}>
        <span className="link-dot" aria-hidden="true" />
        {connected ? "Conectado al quiosco" : "Sin conexión con el quiosco"}
      </span>
    </header>
  );
}

/** Estado del quiosco en una línea: pantalla actual, peso y alerta. */
export function KioskStatus({ snapshot }: { snapshot: Snapshot | null }) {
  if (!snapshot) return <p className="muted">Esperando al quiosco…</p>;
  const w = snapshot.weight;
  return (
    <div className="status">
      <div className="status-screen">
        <span className="status-code">{snapshot.screen === "FUERA_DE_SERVICIO" ? "!" : snapshot.screen}</span>
        <span className="status-name">{SCREEN_NAME[snapshot.screen]}</span>
      </div>
      <dl className="status-facts">
        <div>
          <dt>Productos</dt>
          <dd>{snapshot.item_count}</dd>
        </div>
        <div>
          <dt>Total</dt>
          <dd>S/ {(snapshot.total_cents / 100).toFixed(2)}</dd>
        </div>
        <div>
          <dt>Peso</dt>
          <dd className={w ? (w.ok ? "ok" : "bad") : ""}>
            {w ? (w.ok ? "Coincide" : `${w.diff_g > 0 ? "+" : ""}${w.diff_g} g`) : "—"}
          </dd>
        </div>
      </dl>
      {snapshot.alert && <p className="status-alert">{snapshot.alert}</p>}
    </div>
  );
}
