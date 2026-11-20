import { useState } from "react";
import { post } from "../api";

export function useAction() {
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  /** Llama a la API; devuelve true si salió bien (false si falló o ya había otra en curso). */
  const run = async (path: string, body?: unknown): Promise<boolean> => {
    if (pending) return false;
    setPending(true);
    setError(null);
    try {
      await post(path, body);
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error desconocido");
      return false;
    } finally {
      setPending(false);
    }
  };
  return { error, pending, run };
}
