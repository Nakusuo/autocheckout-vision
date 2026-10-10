import { useEffect, useState } from "react";
import QRCode from "qrcode";
import type { Snapshot } from "../../api";
import { formatPEN } from "../../format";
import { CancelButton } from "../CancelButton";
import { useAction } from "../useAction";
import { Alert } from "./Alert";

export function Pago({ snapshot, offline }: { snapshot: Snapshot; offline: boolean }) {
  const { error, pending, run } = useAction();
  const left = Math.max(0, Math.ceil(120 - snapshot.seconds_in_state));
  const payload = snapshot.qr_payload;
  const [qr, setQr] = useState<{ payload: string; url: string } | null>(null);

  useEffect(() => {
    if (!payload) return;
    let cancelled = false;
    QRCode.toDataURL(payload, { margin: 1, width: 640, errorCorrectionLevel: "M", color: { dark: "#141414", light: "#ffffff" } })
      .then((url) => {
        if (!cancelled) setQr({ payload, url });
      })
      .catch(() => {
        if (!cancelled) setQr(null);
      });
    return () => {
      cancelled = true;
    };
  }, [payload]);

  const dataUrl = qr && qr.payload === payload ? qr.url : null;

  return (
    <section className="screen screen-pay">
      <div className="pay-head">
        <p className="pay-label">Total a pagar</p>
        <p className="amount">{formatPEN(snapshot.total_cents)}</p>
      </div>
      <div className="qr-plate">
        {dataUrl ? (
          <img className="qr-img" src={dataUrl} alt="Código QR de pago" />
        ) : (
          <div className="qr-box">Generando código QR…</div>
        )}
      </div>
      <p className="pay-hint">Escanea con Yape o Plin</p>
      <div className="countdown">
        <p className="speed-sign">{left} s</p>
        <p className="muted waiting">Esperando confirmación del pago</p>
      </div>
      {error && <Alert>{error}</Alert>}
      <CancelButton disabled={offline || pending} onCancel={() => run("/api/cancel")} />
    </section>
  );
}
