import type { Snapshot } from "../../api";
import { CheckDisc } from "../signs";
import { formatDateTime } from "../../format";
import { Lines } from "./Lines";

export function Ticket({ snapshot }: { snapshot: Snapshot }) {
  const left = Math.max(0, Math.ceil(10 - snapshot.seconds_in_state));
  return (
    <section className="screen">
      <div className="thanks">
        <CheckDisc className="thanks-icon" />
        <h1 className="title">Gracias por su compra</h1>
      </div>
      {snapshot.receipt && (
        <div className="receipt">
          <p className="receipt-ok">Cobro exitoso</p>
          <dl className="receipt-data">
            <dt>Boleta</dt>
            <dd>{snapshot.receipt.number}</dd>
            <dt>Fecha</dt>
            <dd>{formatDateTime(snapshot.receipt.issued_at)}</dd>
            {snapshot.receipt.payer && (
              <>
                <dt>Pagó</dt>
                <dd>{snapshot.receipt.payer}</dd>
              </>
            )}
          </dl>
        </div>
      )}
      <Lines snapshot={snapshot} subtotal />
      <div className="countdown">
        <span className="speed-sign" aria-hidden="true">{left}</span>
        <p className="muted">Volviendo al inicio en {left} s</p>
      </div>
    </section>
  );
}
