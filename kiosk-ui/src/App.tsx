import { useKioskState } from "./api";
import { Kiosk } from "./kiosk/Kiosk";

function KioskLive() {
  const { snapshot, connected } = useKioskState();
  if (!snapshot) {
    return <main className="kiosk"><p className="screen screen-center">Conectando...</p></main>;
  }
  return <Kiosk snapshot={snapshot} connected={connected} />;
}

function SimPanel() {
  return <p>Simulador (Task 6)</p>;
}

function CajaPanel() {
  return <p>Caja (Task 6)</p>;
}

export default function App() {
  const path = location.pathname;
  if (path.startsWith("/sim")) return <SimPanel />;
  if (path.startsWith("/caja")) return <CajaPanel />;
  return <KioskLive />;
}
