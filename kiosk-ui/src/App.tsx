import { useKioskState } from "./api";
import { Kiosk } from "./kiosk/Kiosk";
import { AyudaPanel } from "./panels/AyudaPanel";

function KioskLive() {
  const { snapshot, connected } = useKioskState();
  if (!snapshot) {
    return <main className="kiosk"><p className="screen screen-center lead">Conectando…</p></main>;
  }
  return <Kiosk snapshot={snapshot} connected={connected} />;
}

export default function App() {
  const path = location.pathname;
  // Dos vistas: el quiosco (/) y la del encargado con la ayuda y las alertas (/ayuda).
  if (path.startsWith("/ayuda")) return <AyudaPanel />;
  return <KioskLive />;
}
