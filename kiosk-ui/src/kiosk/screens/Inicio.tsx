import { useEffect, useState } from "react";
import { request } from "../../api";
import { formatPEN } from "../../format";
import { ArrowRight } from "../signs";
import { useAction } from "../useAction";

type Item = { sku: string; name: string; price_cents: number };

/** Productos que la cámara reconoce (GET /api/catalog). Si falla, la pizarra no se muestra. */
function useCatalog(): Item[] {
  const [items, setItems] = useState<Item[]>([]);
  useEffect(() => {
    let alive = true;
    request<Item[]>("GET", "/api/catalog")
      .then((list) => {
        if (alive && Array.isArray(list)) setItems(list);
      })
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, []);
  return items;
}

function Board({ items }: { items: Item[] }) {
  const rows = (copy: boolean) =>
    items.map((p) => (
      <li key={`${copy ? "b" : "a"}-${p.sku}`} className="board-row">
        <span className="board-name">{p.name}</span>
        <span className="board-dots" aria-hidden="true" />
        <span className="board-price">{formatPEN(p.price_cents)}</span>
      </li>
    ));
  return (
    <section className="price-board" aria-labelledby="board-title">
      <h2 className="board-title" id="board-title">
        La cámara reconoce {items.length} productos
      </h2>
      <div className="board-window">
        {/* La lista pasa despacio; la segunda copia solo cierra el bucle (oculta al lector). */}
        <div className={`board-track ${items.length > 5 ? "moving" : ""}`} style={{ animationDuration: `${items.length * 2.6}s` }}>
          <ul className="board-list">{rows(false)}</ul>
          {items.length > 5 && <ul className="board-list" aria-hidden="true">{rows(true)}</ul>}
        </div>
      </div>
    </section>
  );
}

export function Inicio({ offline }: { offline: boolean }) {
  const { error, pending, run } = useAction();
  const items = useCatalog();
  return (
    <section className="screen screen-start">
      <div className="start-copy">
        <h1 className="title title-hero"><span className="nowrap">[AUTO-CHECKOUT]</span> Coloca tus productos</h1>
        <p className="lead">Pasa de 1 a 3 productos, uno por uno, frente a la cámara. Sin código de barras.</p>
      </div>
      {items.length > 0 && <Board items={items} />}
      {error && <p className="alert" role="alert">{error}</p>}
      <button type="button" className="btn btn-go" disabled={offline || pending} onClick={() => run("/api/start")}>
        INICIAR
        <ArrowRight className="btn-icon" />
      </button>
    </section>
  );
}
