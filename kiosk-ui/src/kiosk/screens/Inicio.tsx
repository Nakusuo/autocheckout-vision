import { useAction } from "../useAction";

export function Inicio({ offline }: { offline: boolean }) {
  const { error, pending, run } = useAction();
  return (
    <section className="screen screen-center">
      <h1 className="title">[AUTO-CHECKOUT] Coloca tus productos</h1>
      {error && <p className="alert" role="alert">{error}</p>}
      <button type="button" className="btn" disabled={offline || pending} onClick={() => run("/api/start")}>INICIAR</button>
    </section>
  );
}
