import type { CSSProperties } from "react";
import type { Snapshot } from "../../api";
import { formatPEN } from "../../format";

type Props = {
  snapshot: Snapshot;
  subtotal?: boolean;
  /** Productos recién detectados: llevan la marca «+ AGREGADO». */
  added?: Set<string>;
  /** Al volver a escanear, las líneas reaparecen una tras otra. */
  stagger?: boolean;
  /** Avance de la ventana de reescaneo (0 a 1), dibujado como borde superior del tablero. */
  progress?: number;
};

/** Tabla de productos como un letrero de destinos: cantidad en placa negra, nombre y precio unitario. */
export function Lines({ snapshot, subtotal = false, added, stagger = false, progress }: Props) {
  return (
    <div className="board" style={progress === undefined ? undefined : ({ "--scan-progress": progress } as CSSProperties)}>
      {progress !== undefined && <span className="board-progress" aria-hidden="true" />}
      <ul className="lines">
        {snapshot.lines.map((l, i) => (
          <li
            className={`line ${added?.has(l.sku) ? "added" : ""}`}
            key={l.sku}
            style={stagger ? { animationDelay: `${i * 450}ms` } : undefined}
          >
            <span className="line-qty" aria-label="Cantidad">{l.quantity}</span>
            <span className="line-name">
              {l.name}
              {added?.has(l.sku) && <span className="added-tag">+ Agregado</span>}
            </span>
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
