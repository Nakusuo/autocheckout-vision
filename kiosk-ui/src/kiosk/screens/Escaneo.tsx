import type { Snapshot } from "../../api";
import { useAction } from "../useAction";
import { Lines } from "./Lines";

export function Escaneo({ snapshot, offline }: { snapshot: Snapshot; offline: boolean }) {
  const { error, pending, run } = useAction();
  const w = snapshot.weight;
  return (
    <section className="screen">
      <h1 className="title">Escaneando</h1>
      <Lines snapshot={snapshot} />
      {w && (
        <p className={`weight ${w.ok ? "ok" : "bad"}`}>
          {w.ok ? "Peso correcto" : `Peso no coincide (${w.diff_g > 0 ? "+" : ""}${w.diff_g} g)`}
        </p>
      )}
      {snapshot.alert && <p className="alert" role="alert">{snapshot.alert}</p>}
      {error && <p className="alert" role="alert">{error}</p>}
      <button
        type="button"
        className="btn"
        disabled={offline || pending || snapshot.item_count === 0 || snapshot.alert !== null}
        onClick={() => run("/api/confirm")}
      >
        CONFIRMAR
      </button>
    </section>
  );
}
