import type { Snapshot } from "../../api";
import { CancelButton } from "../CancelButton";
import { ArrowRight } from "../signs";
import { useAction } from "../useAction";
import { Alert } from "./Alert";
import { Lines } from "./Lines";

export function Confirmar({ snapshot, offline }: { snapshot: Snapshot; offline: boolean }) {
  const { error, pending, run } = useAction();
  return (
    <section className="screen">
      <h1 className="title">Confirma tu compra</h1>
      <Lines snapshot={snapshot} />
      {snapshot.alert && <Alert>{snapshot.alert}</Alert>}
      {error && <Alert>{error}</Alert>}
      <p className="hint">¿Falta un producto? Pulsa CORREGIR y pásalo por la cámara.</p>
      <div className="actions">
        <button type="button" className="btn btn-go" disabled={offline || pending || !snapshot.can_pay} onClick={() => run("/api/pay")}>
          PAGAR
          <ArrowRight className="btn-icon" />
        </button>
        <button type="button" className="btn btn-plain" disabled={offline || pending} onClick={() => run("/api/correct")}>CORREGIR</button>
        <CancelButton disabled={offline || pending} onCancel={() => run("/api/cancel")} />
      </div>
    </section>
  );
}
