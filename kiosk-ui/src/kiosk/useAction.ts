import { useState } from "react";
import { post } from "../api";

export function useAction() {
  const [error, setError] = useState<string | null>(null);
  const run = async (path: string) => {
    setError(null);
    try {
      await post(path);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error desconocido");
    }
  };
  return { error, run };
}
