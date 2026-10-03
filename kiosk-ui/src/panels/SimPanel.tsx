import { useEffect, useState } from "react";
import { request, useKioskState } from "../api";

type Product = { sku: string; name: string; price_cents: number; weight_g: number };

export function SimPanel() {
  const { snapshot } = useKioskState();
  const [catalog, setCatalog] = useState<Product[]>([]);
  const [qty, setQty] = useState<Record<string, number>>({});
  const [trap, setTrap] = useState("0");
  const [error, setError] = useState<string | null>(null);

  const call = async (method: string, path: string, body?: unknown) => {
    setError(null);
    try {
      await request(method, path, body);
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error desconocido");
      return false;
    }
  };

  useEffect(() => {
    request<Product[]>("GET", "/sim/catalog")
      .then(setCatalog)
      .catch((e) => setError(e instanceof Error ? e.message : "Error desconocido"));
  }, []);

  const change = async (sku: string, delta: number) => {
    const next = { ...qty, [sku]: Math.max(0, (qty[sku] ?? 0) + delta) };
    const skus = catalog.flatMap((p) => Array<string>(next[p.sku] ?? 0).fill(p.sku));
    if (await call("POST", "/sim/tray", { skus })) setQty(next);
  };

  return (
    <main style={{ padding: 16, fontFamily: "system-ui, sans-serif", maxWidth: 640 }}>
      <h1>Simulador (equipo)</h1>
      {error && <p role="alert" style={{ color: "#c62828" }}>{error}</p>}
      <h2>Bandeja</h2>
      <ul style={{ listStyle: "none", padding: 0 }}>
        {catalog.map((p) => (
          <li key={p.sku} style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8 }}>
            <span style={{ flex: 1 }}>{p.name}</span>
            <button type="button" aria-label={`Quitar ${p.name}`} onClick={() => change(p.sku, -1)}>-</button>
            <span aria-label={`Cantidad de ${p.name}`}>{qty[p.sku] ?? 0}</span>
            <button type="button" aria-label={`Añadir ${p.name}`} onClick={() => change(p.sku, 1)}>+</button>
          </li>
        ))}
      </ul>
      <h2>Trampa</h2>
      <label>
        Peso escondido (g){" "}
        <input type="number" value={trap} onChange={(e) => setTrap(e.target.value)} />
      </label>{" "}
      <button type="button" onClick={() => call("POST", "/sim/trap", { offset_g: Number(trap) || 0 })}>Aplicar</button>
      <h2>Pago</h2>
      <button type="button" onClick={() => call("POST", "/sim/pay")}>Simular pago Yape/Plin</button>
      <h2>Estado</h2>
      <p>screen: {snapshot?.screen ?? "-"}</p>
      <p>weight: {snapshot?.weight ? `${snapshot.weight.ok ? "ok" : "no coincide"} (${snapshot.weight.diff_g} g)` : "-"}</p>
      <p>alert: {snapshot?.alert ?? "-"}</p>
    </main>
  );
}
