import type { Snapshot } from "../../api";
import { BRAND } from "../../brand";
import { formatDateTime, formatPEN } from "../../format";
import { CheckDisc, PrinterGlyph } from "../signs";
import { useAction } from "../useAction";
import { Alert } from "./Alert";

/** Segundos que la boleta queda a la vista (RESET_AFTER_S en kiosk-api/service.py). */
export const TICKET_SECONDS = 30;

/**
 * Boleta de la venta pagada (W4), completa como la de una bodega: nombre de la tienda, número,
 * fecha, productos con cantidad y precio, total, cómo se pagó y quién pagó.
 * «Imprimir boleta» usa la impresión del navegador; la hoja de estilos de impresión deja solo la
 * boleta, a 80 mm (ticketera). La boleta es SIMULADA: no se envía a SUNAT y lo dice al pie.
 */
export function Ticket({ snapshot, offline = false }: { snapshot: Snapshot; offline?: boolean }) {
  const { error, pending, run } = useAction();
  const left = Math.max(0, Math.ceil(TICKET_SECONDS - snapshot.seconds_in_state));
  const r = snapshot.receipt;
  const total = r?.total_cents ?? snapshot.total_cents;
  return (
    <section className="screen screen-split screen-ticket">
      <div className="thanks">
        <CheckDisc className="thanks-icon" />
        <div className="thanks-text">
          <h1 className="title">¡Gracias por tu compra!</h1>
          <p className="lead">Cobro exitoso</p>
        </div>
      </div>
      {error && <Alert>{error}</Alert>}
      <div className="actions">
        <button type="button" className="btn btn-go" onClick={() => window.print()}>
          <PrinterGlyph className="btn-icon" />
          IMPRIMIR BOLETA
        </button>
        <button type="button" className="btn btn-plain" disabled={offline || pending} onClick={() => run("/api/new-sale")}>
          NUEVA COMPRA
        </button>
      </div>
      <p className="muted ticket-left">La pantalla vuelve al inicio en {left} s</p>

      {/* En horizontal, la boleta va sola en la columna derecha; en vertical, bajo el agradecimiento. */}
      <div className="split-side">
        <article className="receipt" aria-label="Boleta">
          <header className="receipt-head">
            <p className="receipt-store">{snapshot.store || BRAND}</p>
            {r && (
              <>
                <p className="receipt-kind">
                  Boleta de venta <strong>{r.number}</strong>
                </p>
                <p className="receipt-date">{formatDateTime(r.issued_at)}</p>
              </>
            )}
          </header>
          <table className="receipt-items">
            <thead>
              <tr>
                <th scope="col">Cant.</th>
                <th scope="col">Producto</th>
                <th scope="col">Importe</th>
              </tr>
            </thead>
            <tbody>
              {snapshot.lines.map((l) => (
                <tr key={l.sku}>
                  <td>{l.quantity}</td>
                  <td>
                    {l.name}
                    {l.quantity > 1 && <span className="receipt-unit">{formatPEN(l.unit_price_cents)} c/u</span>}
                  </td>
                  <td>{formatPEN(l.unit_price_cents * l.quantity)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="receipt-total">
            <span>Total</span>
            <span>{formatPEN(total)}</span>
          </p>
          {r && (r.method || r.payer) && (
            <dl className="receipt-data">
              {r.method && (
                <>
                  <dt>Pagó con</dt>
                  <dd>{r.method}</dd>
                </>
              )}
              {r.payer && (
                <>
                  <dt>Cliente</dt>
                  <dd>{r.payer}</dd>
                </>
              )}
            </dl>
          )}
          <p className="receipt-foot">
            Cobrado con {BRAND}, autocobro con cámara. Boleta simulada, sin validez ante SUNAT.
          </p>
        </article>

      </div>
    </section>
  );
}
