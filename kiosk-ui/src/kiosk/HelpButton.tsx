import { useState } from "react";
import { post } from "../api";

export function HelpButton() {
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const ask = async () => {
    setError(null);
    try {
      await post("/api/help");
      setSent(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error desconocido");
    }
  };

  return (
    <div className="help">
      {sent && <p className="help-note">Ayuda en camino</p>}
      {error && <p className="alert" role="alert">{error}</p>}
      <button type="button" className="btn secondary" onClick={ask}>SOLICITAR AYUDA</button>
    </div>
  );
}
