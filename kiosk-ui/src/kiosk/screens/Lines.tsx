import type { Snapshot } from "../../api";
import { formatPEN } from "../../format";

/** Tabla de productos como un letrero de destinos: cantidad en placa negra, nombre y precio unitario. */
export function Lines({ snapshot, subtotal = false }: { snapshot: Snapshot; subtotal?: boolean }) {
  return (
    <div className="board">
      <ul className="lines">
        {snapshot.lines.map((l) => (
          <li className="line" key={l.sku}>
            <span className="line-qty" aria-label="Cantidad">{l.quantity}</span>
            <span className="line-name">{l.name}</span>
            <span className="line-price">{formatPEN(subtotal ? l.unit_price_cents * l.quantity : l.unit_price_cents)}</span>
          </li>
        ))}
      </ul>
      <div className="total">
        <span>Total</span>
        <span className="total-amount">{formatPEN(snapshot.total_cents)}</span>
      </div>
    </div>
  );
}
