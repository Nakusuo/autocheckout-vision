import { useEffect, useState } from "react";
import QRCode from "qrcode";
import type { Snapshot } from "../../api";
import { formatPEN } from "../../format";

export function Pago({ snapshot }: { snapshot: Snapshot }) {
  const left = Math.max(0, Math.ceil(120 - snapshot.seconds_in_state));
  const payload = snapshot.qr_payload;
  const [qr, setQr] = useState<{ payload: string; url: string } | null>(null);

  useEffect(() => {
    if (!payload) return;
    let cancelled = false;
    QRCode.toDataURL(payload, { margin: 1, width: 640, errorCorrectionLevel: "M" })
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
    <section className="screen screen-center">
      <p className="amount">{formatPEN(snapshot.total_cents)}</p>
      {dataUrl ? (
        <img className="qr-img" src={dataUrl} alt="Código QR de pago" />
      ) : (
        <div className="qr-box">Generando código QR…</div>
      )}
      <p>Escanea con Yape o Plin</p>
      <p>Esperando confirmación del pago</p>
      <p className="muted">{left} s</p>
    </section>
  );
}
