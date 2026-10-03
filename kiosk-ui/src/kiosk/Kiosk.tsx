import type { Snapshot } from "../api";
import { HelpButton } from "./HelpButton";
import { Confirmar } from "./screens/Confirmar";
import { Escaneo } from "./screens/Escaneo";
import { Inicio } from "./screens/Inicio";

function Screen({ snapshot }: { snapshot: Snapshot }) {
  switch (snapshot.screen) {
    case "W1":
      return <Inicio />;
    case "W2":
      return <Escaneo snapshot={snapshot} />;
    case "W3":
      return <Confirmar snapshot={snapshot} />;
    default:
      return <p>{snapshot.screen}</p>;
  }
}

export function Kiosk({ snapshot }: { snapshot: Snapshot }) {
  return (
    <main className="kiosk">
      <header className="kiosk-header">AutoCaja</header>
      <Screen snapshot={snapshot} />
      <HelpButton />
    </main>
  );
}
