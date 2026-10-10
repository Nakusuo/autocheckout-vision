import type { Snapshot } from "../api";
import { HelpButton } from "./HelpButton";
import { CautionDiamond } from "./signs";
import { Confirmar } from "./screens/Confirmar";
import { Escaneo } from "./screens/Escaneo";
import { FueraDeServicio } from "./screens/FueraDeServicio";
import { Inicio } from "./screens/Inicio";
import { Pago } from "./screens/Pago";
import { Ticket } from "./screens/Ticket";

const STEPS = ["Coloca", "Confirma", "Paga", "Listo"] as const;
const STEP_OF: Record<Snapshot["screen"], number> = {
  W1: 1,
  W2: 1,
  W3: 2,
  QR: 3,
  W4: 4,
  FUERA_DE_SERVICIO: 0,
};

function Route({ current }: { current: number }) {
  return (
    <ol className="route" aria-label={`Paso ${current} de ${STEPS.length}`}>
      {STEPS.map((label, i) => {
        const n = i + 1;
        const state = n < current ? "done" : n === current ? "now" : "next";
        return (
          <li key={label} className={`route-step ${state}`} aria-current={state === "now" ? "step" : undefined}>
            {/* El número va por CSS (data-n) para no repetir cifras en el texto de la pantalla. */}
            <span className="route-disc" data-n={n} />
            <span className="route-label">{label}</span>
          </li>
        );
      })}
    </ol>
  );
}

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
  const step = STEP_OF[snapshot.screen];
  return (
    <main className="kiosk">
      <header className="kiosk-header">
        <span className="wordmark">Auto<span>Caja</span></span>
        {step > 0 && <Route current={step} />}
      </header>
      {!connected && (
        <p className="notice" role="status">
          <CautionDiamond className="notice-icon" />
          Reconectando…
        </p>
      )}
      {/* La key reinicia la animación: cada estado entra como una placa nueva. */}
      <div className="plate" key={snapshot.screen}>
        <Screen snapshot={snapshot} offline={!connected} />
      </div>
      <HelpButton helpPending={snapshot.help_pending} />
    </main>
  );
}
