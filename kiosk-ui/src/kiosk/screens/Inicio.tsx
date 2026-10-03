import { useAction } from "../useAction";

export function Inicio() {
  const { error, run } = useAction();
  return (
    <section className="screen screen-center">
      <h1 className="title">[AUTO-CHECKOUT] Coloca tus productos</h1>
      {error && <p className="alert" role="alert">{error}</p>}
      <button type="button" className="btn" onClick={() => run("/api/start")}>INICIAR</button>
    </section>
  );
}
