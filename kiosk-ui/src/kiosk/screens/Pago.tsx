import type { Snapshot } from "../../api";
import { formatPEN } from "../../format";

export function Pago({ snapshot }: { snapshot: Snapshot }) {
  const left = Math.max(0, Math.ceil(120 - snapshot.seconds_in_state));
  return (
    <section className="screen screen-center">
      <p className="amount">{formatPEN(snapshot.total_cents)}</p>
      <div className="qr-box">Aquí aparecerá el código QR (M3)</div>
      <p>Esperando confirmación del pago</p>
      <p className="muted">{left} s</p>
    </section>
  );
}
