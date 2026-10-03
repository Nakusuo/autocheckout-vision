import type { Snapshot } from "../../api";
import { formatPEN } from "../../format";

export function Ticket({ snapshot }: { snapshot: Snapshot }) {
  const left = Math.max(0, Math.ceil(10 - snapshot.seconds_in_state));
  return (
    <section className="screen">
      <h1 className="title">Gracias por su compra</h1>
      <ul className="lines">
        {snapshot.lines.map((l) => (
          <li className="line" key={l.sku}>
            <span>{l.name}</span>
            <span className="line-qty" aria-label="Cantidad">{l.quantity}</span>
            <span>{formatPEN(l.unit_price_cents * l.quantity)}</span>
          </li>
        ))}
      </ul>
      <div className="total">
        <span>Total</span>
        <span>{formatPEN(snapshot.total_cents)}</span>
      </div>
      <p className="muted">Volviendo al inicio en {left} s</p>
    </section>
  );
}
