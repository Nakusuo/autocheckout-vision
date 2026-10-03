import type { Snapshot } from "../api";
import { HelpButton } from "./HelpButton";
import { Confirmar } from "./screens/Confirmar";
import { Escaneo } from "./screens/Escaneo";
import { FueraDeServicio } from "./screens/FueraDeServicio";
import { Inicio } from "./screens/Inicio";
import { Pago } from "./screens/Pago";
import { Ticket } from "./screens/Ticket";

function Screen({ snapshot, offline }: { snapshot: Snapshot; offline: boolean }) {
  switch (snapshot.screen) {
    case "W1":
      return <Inicio offline={offline} />;
    case "W2":
      return <Escaneo snapshot={snapshot} offline={offline} />;
    case "W3":
      return <Confirmar snapshot={snapshot} offline={offline} />;
    case "QR":
      return <Pago snapshot={snapshot} />;
    case "W4":
      return <Ticket snapshot={snapshot} />;
    case "FUERA_DE_SERVICIO":
      return <FueraDeServicio />;
  }
}

export function Kiosk({ snapshot, connected = true }: { snapshot: Snapshot; connected?: boolean }) {
  return (
    <main className="kiosk">
      <header className="kiosk-header">AutoCaja</header>
      {!connected && <p className="alert" role="status">Reconectando…</p>}
      <Screen snapshot={snapshot} offline={!connected} />
      <HelpButton helpPending={snapshot.help_pending} />
    </main>
  );
}
