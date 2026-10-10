import { useEffect, useState } from "react";
import type { Snapshot } from "../../api";
import { CancelButton } from "../CancelButton";
import { ArrowRight, CheckDisc, TraySign } from "../signs";
import { useAction } from "../useAction";
import { Alert } from "./Alert";
import { Lines } from "./Lines";

const TICK_MS = 300;
const ADDED_TICKS = 8; // ≈ 2,4 s con la marca «+ Agregado»

/** Productos cuya cantidad acaba de subir: se marcan como «agregados» unos segundos. */
function useRecentlyAdded(lines: Snapshot["lines"]): Set<string> {
  const [added, setAdded] = useState<Record<string, number>>({});

  // Se compara con el snapshot anterior durante el render (patrón de React para estado derivado).
  const [prevLines, setPrevLines] = useState(lines);
  if (lines !== prevLines) {
    setPrevLines(lines);
    const before = Object.fromEntries(prevLines.map((l) => [l.sku, l.quantity]));
    const grew = lines.filter((l) => l.quantity > (before[l.sku] ?? 0)).map((l) => l.sku);
    if (grew.length > 0) {
      setAdded((a) => ({ ...a, ...Object.fromEntries(grew.map((sku) => [sku, ADDED_TICKS])) }));
    }
  }

  // El snapshot llega varias veces por segundo: las marcas se limpian aparte, no al recibirlo.
  useEffect(() => {
    const prune = setInterval(() => {
      setAdded((a) => {
        if (Object.keys(a).length === 0) return a;
        return Object.fromEntries(
          Object.entries(a)
            .map(([sku, left]) => [sku, left - 1] as const)
            .filter(([, left]) => left > 0),
        );
      });
    }, TICK_MS);
    return () => clearInterval(prune);
  }, []);

  return new Set(Object.keys(added));
}

export function Escaneo({ snapshot, offline }: { snapshot: Snapshot; offline: boolean }) {
  const { error, pending, run } = useAction();
  const w = snapshot.weight;
  const empty = snapshot.lines.length === 0;
  const added = useRecentlyAdded(snapshot.lines);

  return (
    <section className="screen">
      <div className="scan-head">
        <h1 className="title">Escaneando</h1>
        <span className="live">
          <span className="live-dot" aria-hidden="true" />
          En vivo
        </span>
      </div>
      {empty ? (
        <div className="empty">
          <TraySign className="empty-sign" scanning />
          <p className="lead">Pasa tus productos uno por uno frente a la cámara. Cada uno se suma aquí.</p>
        </div>
      ) : (
        <Lines
          snapshot={snapshot}
          added={added}
          onRemove={(sku) => run("/api/remove", { sku })}
          removeDisabled={offline || pending}
        />
      )}
      {w && !empty && !snapshot.alert && (
        <p className={`weight ${w.ok ? "ok" : "pending"}`}>
          {w.ok ? <CheckDisc className="weight-icon" /> : <span className="weight-pending" aria-hidden="true" />}
          <span>{w.ok ? "Peso correcto" : "Pesando la bandeja…"}</span>
        </p>
      )}
      {snapshot.alert && <Alert>{snapshot.alert}</Alert>}
      {error && <Alert>{error}</Alert>}
      {!empty && !snapshot.alert && (
        <p className="hint">Pasa el siguiente producto o pulsa CONFIRMAR si ya están todos.</p>
      )}
      <button
        type="button"
        className="btn btn-go"
        disabled={offline || pending || snapshot.item_count === 0 || snapshot.alert !== null || !w?.ok}
        onClick={() => run("/api/confirm")}
      >
        CONFIRMAR
        <ArrowRight className="btn-icon" />
      </button>
      <CancelButton disabled={offline || pending} onCancel={() => run("/api/cancel")} />
    </section>
  );
}
