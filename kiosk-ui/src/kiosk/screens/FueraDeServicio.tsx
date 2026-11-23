import { StopOctagon } from "../signs";

export function FueraDeServicio() {
  return (
    <section className="screen screen-center">
      <StopOctagon className="stop-sign" />
      <h1 className="title title-hero">Fuera de servicio</h1>
      <p className="lead">Acércate al mostrador, ya te atendemos.</p>
    </section>
  );
}
