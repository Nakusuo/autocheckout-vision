import { useState } from "react";
import { post } from "../api";

export function HelpButton({ helpPending }: { helpPending: boolean }) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const ask = async () => {
    if (pending) return;
    setPending(true);
    setError(null);
    try {
      await post("/api/help");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error desconocido");
    } finally {
      setPending(false);
    }
  };

  return (
    <div className="help">
      {helpPending && <p className="help-note" role="status">Ayuda en camino</p>}
      {error && <p className="alert" role="alert">{error}</p>}
      <button type="button" className="btn secondary" disabled={pending} onClick={ask}>SOLICITAR AYUDA</button>
    </div>
  );
}
