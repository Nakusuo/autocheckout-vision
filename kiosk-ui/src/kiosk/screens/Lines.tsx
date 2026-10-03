import type { Snapshot } from "../../api";
import { formatPEN } from "../../format";

export function Lines({ snapshot }: { snapshot: Snapshot }) {
  return (
    <>
      <ul className="lines">
        {snapshot.lines.map((l) => (
          <li className="line" key={l.sku}>
            <span>{l.name}</span>
            <span className="line-qty" aria-label="Cantidad">{l.quantity}</span>
            <span>{formatPEN(l.unit_price_cents)}</span>
          </li>
        ))}
      </ul>
      <div className="total">
        <span>Total</span>
        <span>{formatPEN(snapshot.total_cents)}</span>
      </div>
    </>
  );
}
