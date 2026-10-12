import { ArrowRight, TraySign } from "../signs";
import { useAction } from "../useAction";

export function Inicio({ offline }: { offline: boolean }) {
  const { error, pending, run } = useAction();
  return (
    <section className="screen screen-start">
      <TraySign className="hero-sign" />
      <h1 className="title title-hero"><span className="nowrap">[AUTO-CHECKOUT]</span> Coloca tus productos</h1>
      <p className="lead">Pasa de 1 a 3 productos, uno por uno, frente a la cámara. Ella los va sumando.</p>
      {error && <p className="alert" role="alert">{error}</p>}
      <button type="button" className="btn btn-go" disabled={offline || pending} onClick={() => run("/api/start")}>
        INICIAR
        <ArrowRight className="btn-icon" />
      </button>
    </section>
  );
}
