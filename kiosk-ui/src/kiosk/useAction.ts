import { useState } from "react";
import { post } from "../api";

export function useAction() {
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const run = async (path: string, body?: unknown) => {
    if (pending) return;
    setPending(true);
    setError(null);
    try {
      await post(path, body);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error desconocido");
    } finally {
      setPending(false);
    }
  };
  return { error, pending, run };
}
