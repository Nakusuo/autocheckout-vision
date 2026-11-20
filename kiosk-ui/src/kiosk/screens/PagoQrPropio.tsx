import type { Snapshot } from "../../api";
import { formatPEN } from "../../format";
import { CancelButton } from "../CancelButton";
import { useAction } from "../useAction";
import { Alert } from "./Alert";

/**
 * Pago con el QR propio de Yape/Plin del comercio. El QR es estático (el de su app): el cliente
 * escribe el monto en su Yape. El quiosco espera la notificación de pago recibido.
 */
export function PagoQrPropio({ snapshot, offline }: { snapshot: Snapshot; offline: boolean }) {
  const { error, pending, run } = useAction();
  const left = Math.max(0, Math.ceil(120 - snapshot.seconds_in_state));
  return (
    <section className="screen screen-pay screen-pay-own">
      <div className="qr-plate">
        {snapshot.wallet_qr ? (
          <img className="qr-img qr-wallet" src={snapshot.wallet_qr} alt="Código QR de Yape del comercio" />
        ) : (
          <div className="qr-box">Falta el QR del comercio</div>
        )}
      </div>
      {/* En vertical, pay-info no existe para el diseño (display: contents) y el monto sube
          arriba del QR; en horizontal es la columna derecha. */}
      <div className="pay-info">
        <div className="pay-head">
          <p className="pay-label">Total a pagar</p>
          <p className="amount">{formatPEN(snapshot.total_cents)}</p>
        </div>
        {/* El QR es fijo: el monto lo escribe el cliente, y el pago solo se acepta si coincide. */}
        <ol className="pay-steps">
          <li className="pay-step">
            <span className="pay-step-n" aria-hidden="true">1</span>
            <span className="pay-hint">Escanea con Yape o Plin</span>
          </li>
          <li className="pay-step">
            <span className="pay-step-n" aria-hidden="true">2</span>
            <span className="pay-hint">Escribe exactamente {formatPEN(snapshot.total_cents).replace(" ", "\u00a0")}</span>
          </li>
        </ol>
        <div className="countdown">
          <p className="speed-sign">{left} s</p>
          <p className="muted waiting">Esperando la confirmación del pago</p>
        </div>
        {error && <Alert>{error}</Alert>}
        <CancelButton disabled={offline || pending} onCancel={() => run("/api/cancel")} />
      </div>
    </section>
  );
}
