import type { Snapshot } from "../../api";
import { formatPEN } from "../../format";

type Props = {
  snapshot: Snapshot;
  subtotal?: boolean;
  /** Productos recién escaneados: llevan la marca «+ Agregado». */
  added?: Set<string>;
  /** Si se pasa, cada línea tiene «Quitar» (quita una unidad). */
  onRemove?: (sku: string) => void;
  removeDisabled?: boolean;
};

/** Tabla de productos como un letrero de destinos: cantidad en placa negra, nombre y precio unitario. */
export function Lines({ snapshot, subtotal = false, added, onRemove, removeDisabled = false }: Props) {
  return (
    <div className="board">
      <ul className="lines">
        {snapshot.lines.map((l) => (
          <li className={`line ${added?.has(l.sku) ? "added" : ""} ${onRemove ? "removable" : ""}`} key={l.sku}>
            <span className="line-qty" aria-label="Cantidad">{l.quantity}</span>
            <span className="line-name">
              {l.name}
              {added?.has(l.sku) && <span className="added-tag">+ Agregado</span>}
            </span>
            <span className="line-price">{formatPEN(subtotal ? l.unit_price_cents * l.quantity : l.unit_price_cents)}</span>
            {onRemove && (
              <button
                type="button"
                className="line-remove"
                aria-label={`Quitar uno de ${l.name}`}
                disabled={removeDisabled}
                onClick={() => onRemove(l.sku)}
              >
                <span aria-hidden="true">−</span>
              </button>
            )}
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
