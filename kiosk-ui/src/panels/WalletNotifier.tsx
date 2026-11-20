import { useState } from "react";
import { request, type Snapshot } from "../api";
import { formatPEN } from "../format";

type Result = { matched: boolean; reason?: string; receipt?: string };

/**
 * Simula la notificación «Fulano te yapeó S/ …» que llega al celular del comercio cuando pagan
 * a su QR de Yape/Plin. En la app Android esa notificación la leerá el propio celular.
 */
export function WalletNotifier({ snapshot }: { snapshot: Snapshot | null }) {
  const [text, setText] = useState("");
  const [result, setResult] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const waiting = snapshot?.screen === "QR";
  const suggested = `Juan Pérez te yapeó ${formatPEN(snapshot?.total_cents ?? 0)}`;

  const send = async () => {
    setSending(true);
    setResult(null);
    try {
      const r = await request<Result>("POST", "/sim/wallet-notification", { text: text || suggested });
      setResult(r.matched ? `Pago aceptado: boleta ${r.receipt}` : `No se aceptó: ${r.reason}`);
    } catch (e) {
      setResult(e instanceof Error ? e.message : "Error desconocido");
    } finally {
      setSending(false);
    }
  };

  return (
    <section className="card">
      <h2 className="card-title">Notificación de Yape</h2>
      <p className="muted">
        Simula el aviso que llega a tu celular cuando alguien paga a tu QR. Cambia el monto para probar un pago que no coincide.
      </p>
      <label className="field">
        <span>Texto de la notificación</span>
        <input type="text" value={text} placeholder={suggested} maxLength={500} onChange={(e) => setText(e.target.value)} />
      </label>
      <button type="button" className="pbtn go" disabled={sending} onClick={send}>
        Simular yapeo recibido
      </button>
      {!waiting && <p className="muted">El quiosco aún no muestra el QR: la notificación no se aceptará.</p>}
      {result && <p role="status">{result}</p>}
    </section>
  );
}
