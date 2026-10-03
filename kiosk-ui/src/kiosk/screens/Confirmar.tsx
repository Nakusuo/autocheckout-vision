import type { Snapshot } from "../../api";
import { useAction } from "../useAction";
import { Lines } from "./Lines";

export function Confirmar({ snapshot }: { snapshot: Snapshot }) {
  const { error, run } = useAction();
  return (
    <section className="screen">
      <h1 className="title">Confirma tu compra</h1>
      <Lines snapshot={snapshot} />
      {snapshot.alert && <p className="alert" role="alert">{snapshot.alert}</p>}
      {error && <p className="alert" role="alert">{error}</p>}
      <div className="actions">
        <button type="button" className="btn" disabled={!snapshot.can_pay} onClick={() => run("/api/pay")}>PAGAR</button>
        <button type="button" className="btn secondary" onClick={() => run("/api/correct")}>CORREGIR</button>
      </div>
    </section>
  );
}
