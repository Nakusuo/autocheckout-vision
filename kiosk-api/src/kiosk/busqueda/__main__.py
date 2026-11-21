"""Comparación de algoritmos de búsqueda sobre los problemas del quiosco.

    python -m kiosk.busqueda                 # flujo W1–W4 y pesos de ejemplo
    python -m kiosk.busqueda --peso 238.0    # identifica productos para un peso medido
    python -m kiosk.busqueda --umbral ../ml/data/apf3/pares.csv   # ajusta umbrales (Hill Climbing)
"""

import argparse
import csv
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
from kiosk.busqueda.problemas import (
    FlujoCompra,
    PesoBandeja,
    UmbralReconocedor,
    alcanzables,
    sin_salida,
)
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


UMBRAL_HOY, MARGEN_HOY = 1.2, 0.05  # kiosk.recognizer: BOX_THRESHOLD, BOX_MARGIN


def leer_pares(path: Path) -> list[tuple[float, float, int, str]]:
    """Casos medidos (parecido, margen, conocido, sku) que escribe `python -m mltools.apf3 informe`."""
    with path.open(encoding="utf-8") as f:
        return [
            (float(r["parecido"]), float(r["margen"]), int(r["conocido"]), r["sku"])
            for r in csv.DictReader(f)
        ]


def _f1(aciertos: list[tuple[bool, int]]) -> float:
    vp = sum(a and c == 1 for a, c in aciertos)
    fp = sum(a and c == 0 for a, c in aciertos)
    fn = sum(not a and c == 1 for a, c in aciertos)
    return 2 * vp / (2 * vp + fp + fn) if vp else 0.0


def ajustar_umbrales(pares: list[tuple[float, float, int, str]]) -> dict:
    """Hill Climbing frente a la búsqueda exhaustiva y frente a la regla fija de hoy.

    - Con todos los casos: cuánto F1 logra cada uno y cuántas evaluaciones gasta.
    - Fuera de muestra (por producto): se ajusta sin un producto y se prueba con él; así se ve si
      los umbrales aprendidos sirven para productos que no vio, no solo para estos datos.
    """
    problema = UmbralReconocedor((p, m, c) for p, m, c, _ in pares)
    hoy = UmbralReconocedor.estado(UMBRAL_HOY, MARGEN_HOY)
    hc = hill_climbing(hoy, problema.neighbors, problema.score)
    hr = hill_climbing_restarts(problema.random_state, problema.neighbors, problema.score, 10)
    mejor, f1_max = problema.exhaustiva()

    fijo, aprendido = [], []
    for sku in sorted({s for *_, s in pares}):
        entreno = UmbralReconocedor((p, m, c) for p, m, c, s in pares if s != sku)
        estado = hill_climbing_restarts(
            entreno.random_state, entreno.neighbors, entreno.score, 10
        ).state
        for p, m, c, s in pares:
            if s == sku:
                fijo.append((entreno.acepta(hoy, p, m), c))
                aprendido.append((entreno.acepta(estado, p, m), c))
    return {
        "hoy": (UmbralReconocedor.valores(hoy), problema.score(hoy)),
        "hc": (UmbralReconocedor.valores(hc.state), hc.score, hc.evaluations),
        "hc_reinicios": (UmbralReconocedor.valores(hr.state), hr.score, hr.evaluations),
        "exhaustiva": (UmbralReconocedor.valores(mejor), f1_max, 51 * 31),
        "fuera_de_muestra": {"regla_fija": _f1(fijo), "hill_climbing": _f1(aprendido)},
    }


def _umbrales(path: Path) -> None:
    r = ajustar_umbrales(leer_pares(path))
    (u, m), f1 = r["hoy"]
    print(f"== Umbrales del reconocedor ({path.name}) ==")
    print(f"Hoy    parecido ≥ {u:.2f}, margen ≥ {m:.2f}  F1={f1:.3f}")
    for nombre, clave in (("HC", "hc"), ("HC x10", "hc_reinicios"), ("Todos", "exhaustiva")):
        (u, m), f1, ev = r[clave]
        print(f"{nombre:<6} parecido ≥ {u:.2f}, margen ≥ {m:.2f}  F1={f1:.3f}  evaluaciones={ev}")
    fuera = r["fuera_de_muestra"]
    print(
        f"Fuera de muestra (por producto): regla fija F1={fuera['regla_fija']:.3f} · "
        f"Hill Climbing F1={fuera['hill_climbing']:.3f}"
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--peso", type=float, default=238.0, help="peso medido en gramos")
    ap.add_argument("--umbral", type=Path, help="pares.csv de mltools.apf3: ajusta los umbrales")
    args = ap.parse_args(argv)
    if args.umbral is not None:
        if not args.umbral.is_file():
            ap.exit(1, f"No existe {args.umbral}: corre antes «python -m mltools.apf3 informe»\n")
        _umbrales(args.umbral)
        return 0

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
