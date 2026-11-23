import { ArrowRight, DemoVisor } from "../signs";
import { useAction } from "../useAction";

export function Inicio({ offline }: { offline: boolean }) {
  const { error, pending, run } = useAction();
  return (
    <section className="screen screen-start">
      <DemoVisor className="hero-demo" />
      <h1 className="title title-hero"><span className="nowrap">[AUTO-CHECKOUT]</span> Coloca tus productos</h1>
      {/* Cómo funciona, en tres pasos: la cámara reconoce cada producto, sin códigos de barras. */}
      <ol className="how">
        <li className="how-step"><span className="how-n" aria-hidden="true">1</span>Pasa de 1 a 3 productos, uno por uno</li>
        <li className="how-step"><span className="how-n" aria-hidden="true">2</span>La cámara los reconoce, sin código de barras</li>
        <li className="how-step"><span className="how-n" aria-hidden="true">3</span>Pagas con Yape o Plin</li>
      </ol>
      {error && <p className="alert" role="alert">{error}</p>}
      <button type="button" className="btn btn-go" disabled={offline || pending} onClick={() => run("/api/start")}>
        INICIAR
        <ArrowRight className="btn-icon" />
      </button>
    </section>
  );
}
