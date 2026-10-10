import type { Snapshot } from "../../api";
import { ArrowRight, CautionDiamond, CheckDisc, RescanGlyph, TraySign } from "../signs";
import { useAction } from "../useAction";
import { Alert } from "./Alert";
import { Lines } from "./Lines";

export function Escaneo({ snapshot, offline }: { snapshot: Snapshot; offline: boolean }) {
  const { error, pending, run } = useAction();
  const w = snapshot.weight;
  const empty = snapshot.lines.length === 0;
  return (
    <section className="screen">
      <h1 className="title">Escaneando</h1>
      {empty ? (
        <div className="empty">
          <TraySign className="empty-sign" scanning />
          <p className="lead">Deja tus productos en la bandeja, sin apilarlos.</p>
        </div>
      ) : (
        <Lines snapshot={snapshot} />
      )}
      {w && !empty && !snapshot.alert && (
        <p className={`weight ${w.ok ? "ok" : "bad"}`}>
          {w.ok ? <CheckDisc className="weight-icon" /> : <CautionDiamond className="weight-icon" />}
          <span>{w.ok ? "Peso correcto" : `Peso no coincide (${w.diff_g > 0 ? "+" : ""}${w.diff_g} g)`}</span>
        </p>
      )}
      {snapshot.alert && <Alert>{snapshot.alert}</Alert>}
      {error && <Alert>{error}</Alert>}
      <button
        type="button"
        className="btn btn-go"
        disabled={offline || pending || snapshot.item_count === 0 || snapshot.alert !== null}
        onClick={() => run("/api/confirm")}
      >
        CONFIRMAR
        <ArrowRight className="btn-icon" />
      </button>
      <button type="button" className="btn btn-plain btn-small" disabled={offline || pending} onClick={() => run("/api/rescan")}>
        <RescanGlyph className="btn-icon" />
        VOLVER A ESCANEAR
      </button>
    </section>
  );
}
