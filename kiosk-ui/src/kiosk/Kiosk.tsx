import type { Snapshot } from "../api";
import { HelpButton } from "./HelpButton";
import { Confirmar } from "./screens/Confirmar";
import { Escaneo } from "./screens/Escaneo";
import { Inicio } from "./screens/Inicio";

function Screen({ snapshot, offline }: { snapshot: Snapshot; offline: boolean }) {
  switch (snapshot.screen) {
    case "W1":
      return <Inicio offline={offline} />;
    case "W2":
      return <Escaneo snapshot={snapshot} offline={offline} />;
    case "W3":
      return <Confirmar snapshot={snapshot} offline={offline} />;
    default:
      return <p>{snapshot.screen}</p>;
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
