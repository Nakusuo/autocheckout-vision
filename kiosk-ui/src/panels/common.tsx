import "./panels.css";

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
