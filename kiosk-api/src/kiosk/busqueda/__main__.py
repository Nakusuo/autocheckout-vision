"""Comparación de algoritmos de búsqueda sobre los problemas del quiosco.

    python -m kiosk.busqueda                 # flujo W1–W4 y pesos de ejemplo
    python -m kiosk.busqueda --peso 238.0    # identifica productos para un peso medido
"""

import argparse
import random
import time
from collections.abc import Callable
from pathlib import Path

from kiosk.busqueda.algoritmos import (
    SearchResult,
    a_star,
    bfs,
    dfs,
    hill_climbing,
    hill_climbing_restarts,
)
from kiosk.busqueda.problemas import FlujoCompra, PesoBandeja, alcanzables, sin_salida
from kiosk.catalog import Catalog

CATALOG = Path(__file__).resolve().parents[4] / "catalog" / "products.csv"


def _row(name: str, run: Callable[[], SearchResult]) -> str:
    t0 = time.perf_counter()
    r = run()
    ms = (time.perf_counter() - t0) * 1000
    plan = " -> ".join(map(str, r.actions)) if r.found else "sin solución"
    return (
        f"{name:<6} coste={r.cost:<4g} expandidos={r.expanded:<5} generados={r.generated:<5} "
        f"frontera={r.max_frontier:<4} {ms:6.2f} ms  {plan}"
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--peso", type=float, default=238.0, help="peso medido en gramos")
    args = ap.parse_args(argv)

    flujo = FlujoCompra()
    print(f"== Flujo de compra: {len(alcanzables(flujo))} estados alcanzables, "
          f"{len(sin_salida(flujo))} sin salida ==")
    for name, run in (("BFS", lambda: bfs(flujo)), ("DFS", lambda: dfs(flujo)),
                      ("A*", lambda: a_star(flujo))):
        print(_row(name, run))

    catalog = Catalog.from_csv(CATALOG)
    peso = PesoBandeja(catalog, args.peso)
    print(f"\n== ¿Qué hay en la bandeja? peso medido {args.peso:g} g (±{peso.tolerance_g:g} g) ==")
    for name, run in (("BFS", lambda: bfs(peso)), ("DFS", lambda: dfs(peso)),
                      ("A*", lambda: a_star(peso))):
        print(_row(name, run))
    rng = random.Random(1)  # nosec B311: semilla fija para una demo reproducible
    hc = hill_climbing(peso.random_state(rng), peso.neighbors, peso.score)
    print(f"HC     estado={hc.state} error={-hc.score:.1f} g pasos={hc.steps} evaluaciones={hc.evaluations}")
    hr = hill_climbing_restarts(peso.random_state, peso.neighbors, peso.score, restarts=10)
    print(f"HC x10 estado={hr.state} error={-hr.score:.1f} g evaluaciones={hr.evaluations}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
