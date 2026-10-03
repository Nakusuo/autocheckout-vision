import { useKioskState } from "./api";
import { Kiosk } from "./kiosk/Kiosk";
import { CajaPanel } from "./panels/CajaPanel";
import { SimPanel } from "./panels/SimPanel";

function KioskLive() {
  const { snapshot, connected } = useKioskState();
  if (!snapshot) {
    return <main className="kiosk"><p className="screen screen-center">Conectando...</p></main>;
  }
  return <Kiosk snapshot={snapshot} connected={connected} />;
}

export default function App() {
  const path = location.pathname;
  if (path.startsWith("/sim")) return <SimPanel />;
  if (path.startsWith("/caja")) return <CajaPanel />;
  return <KioskLive />;
}
