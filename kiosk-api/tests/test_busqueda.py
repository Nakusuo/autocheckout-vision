import random
from typing import ClassVar

import pytest

from kiosk.busqueda.__main__ import main
from kiosk.busqueda.algoritmos import a_star, bfs, dfs, hill_climbing, hill_climbing_restarts
from kiosk.busqueda.problemas import FlujoCompra, PesoBandeja, alcanzables, sin_salida
from kiosk.catalog import Catalog, Product
from kiosk.checkout import State as Screen


class Grafo:
    """Grafo pequeño con pesos: el camino corto en pasos (A-D) no es el más barato (A-B-C-D)."""

    EDGES: ClassVar[dict] = {"A": [("B", 1), ("D", 10)], "B": [("C", 1)], "C": [("D", 1)], "D": [], "Z": []}

    def __init__(self, goal="D", cyclic=False):
        self.goal = goal
        self.edges = dict(self.EDGES)
        if cyclic:
            self.edges["C"] = [("D", 1), ("A", 1)]

    def initial_state(self):
        return "A"

    def is_goal(self, state):
        return state == self.goal

    def successors(self, state):
        return [(f"{state}->{n}", n, c) for n, c in self.edges[state]]

    def heuristic(self, state):
        return {"A": 3, "B": 2, "C": 1, "D": 0, "Z": 0}[state]


def test_bfs_minimiza_pasos_no_coste():
    r = bfs(Grafo())
    assert r.found and r.actions == ("A->D",) and r.cost == 10


def test_a_star_minimiza_coste():
    r = a_star(Grafo())
    assert r.found and r.cost == 3 and r.actions == ("A->B", "B->C", "C->D")


def test_dfs_encuentra_un_camino_y_tolera_ciclos():
    r = dfs(Grafo(cyclic=True))
    assert r.found and r.actions[-1].endswith("->D")


def test_dfs_con_limite_de_profundidad():
    assert dfs(Grafo(), depth_limit=1).found  # A->D está a profundidad 1
    assert not dfs(Grafo(goal="C"), depth_limit=1).found  # C está a profundidad 2


def test_meta_inalcanzable_y_meta_en_el_inicio():
    for algoritmo in (bfs, dfs, a_star):
        assert not algoritmo(Grafo(goal="Z")).found
    assert bfs(Grafo(goal="A")) == bfs(Grafo(goal="A")) and bfs(Grafo(goal="A")).cost == 0


def test_a_star_poda_heuristica_infinita():
    class Podado(Grafo):
        def heuristic(self, state):
            return float("inf") if state == "B" else 1

    assert a_star(Podado()).actions == ("A->D",)


# --- Flujo de compra (usa el Checkout real) ---


def test_el_camino_mas_corto_a_w4_son_cinco_acciones():
    for algoritmo in (bfs, a_star):
        r = algoritmo(FlujoCompra())
        assert r.actions == ("iniciar", "agregar", "confirmar", "pagar", "pago_ok")


def test_dfs_llega_a_w4_pero_no_garantiza_el_camino_corto():
    r = dfs(FlujoCompra())
    assert r.found and r.cost >= 5


def test_a_star_expande_menos_que_bfs_en_el_flujo():
    assert a_star(FlujoCompra()).expanded < bfs(FlujoCompra()).expanded


def test_todos_los_estados_alcanzables_tienen_salida():
    flujo = FlujoCompra()
    assert (Screen.OUT_OF_SERVICE, 0) in alcanzables(flujo)
    assert sin_salida(flujo) == set()


def test_no_se_puede_confirmar_con_cuatro_productos_ni_pagar_desde_w1():
    flujo = FlujoCompra()
    acciones = {a for a, _, _ in flujo.successors((Screen.SCANNING, 4))}
    assert "confirmar" not in acciones and "quitar" in acciones
    assert {a for a, _, _ in flujo.successors((Screen.IDLE, 0))} == {"iniciar", "falla"}


# --- Peso de la bandeja ---


@pytest.fixture
def catalogo():
    return Catalog(
        [
            Product("A", "A", 100, 20.0),
            Product("B", "B", 100, 50.0),
            Product("C", "C", 100, 200.0),
        ]
    )


def test_a_star_encuentra_la_combinacion_con_menos_productos(catalogo):
    r = a_star(PesoBandeja(catalogo, 250.0))
    assert r.found and r.actions == ("B", "C") and r.cost == 2


def test_bfs_y_a_star_coinciden_en_coste(catalogo):
    for peso in (20.0, 70.0, 270.0, 450.0):
        problema = PesoBandeja(catalogo, peso)
        assert bfs(problema).cost == a_star(problema).cost


def test_tolerancia_de_cinco_gramos(catalogo):
    assert a_star(PesoBandeja(catalogo, 205.0)).found  # 200 + 5
    assert not a_star(PesoBandeja(catalogo, 206.0)).found


def test_peso_imposible_no_tiene_solucion(catalogo):
    assert not a_star(PesoBandeja(catalogo, 5000.0)).found
    assert not bfs(PesoBandeja(catalogo, 1.0)).found


def test_heuristica_es_admisible(catalogo):
    """h(n) nunca supera el coste real que falta hasta la meta."""
    problema = PesoBandeja(catalogo, 450.0)
    for estado in [(), ("A",), ("C",), ("B", "C")]:
        h = problema.heuristic(estado)
        if h == float("inf"):
            continue
        sub = PesoBandeja(catalogo, 450.0)
        sub.initial_state = lambda e=estado: e  # type: ignore[method-assign]
        real = bfs(sub)
        if real.found:
            assert h <= real.cost


# --- Hill Climbing ---


def test_hill_climbing_sube_hasta_un_optimo_local(catalogo):
    problema = PesoBandeja(catalogo, 250.0)
    r = hill_climbing(("A",), problema.neighbors, problema.score)
    assert r.score >= problema.score(("A",)) and r.steps >= 1


def test_hill_climbing_se_queda_en_el_optimo_si_no_hay_mejora():
    r = hill_climbing(5, lambda x: [x - 1, x + 1], lambda x: -abs(x - 5))
    assert r.state == 5 and r.steps == 0


def test_hill_climbing_respeta_max_steps():
    r = hill_climbing(0, lambda x: [x + 1], lambda x: x, max_steps=3)
    assert r.state == 3 and r.steps == 3


def test_reinicios_escapan_de_un_maximo_local():
    # Dos colinas: máximo local en x=2 (valor 5) y global en x=8 (valor 10).
    def score(x):
        return 5 - abs(x - 2) if x < 5 else 10 - abs(x - 8)

    def vecinos(x):
        return [v for v in (x - 1, x + 1) if 0 <= v <= 10]

    atrapado = hill_climbing(0, vecinos, score)
    assert atrapado.state == 2
    mejor = hill_climbing_restarts(lambda rng: rng.randint(0, 10), vecinos, score, restarts=20, seed=3)
    assert mejor.state == 8 and mejor.score == 10


def test_reinicios_son_reproducibles(catalogo):
    problema = PesoBandeja(catalogo, 270.0)
    a = hill_climbing_restarts(problema.random_state, problema.neighbors, problema.score, 5, seed=7)
    b = hill_climbing_restarts(problema.random_state, problema.neighbors, problema.score, 5, seed=7)
    assert a == b


def test_estado_aleatorio_respeta_el_maximo(catalogo):
    problema = PesoBandeja(catalogo, 100.0)
    rng = random.Random(1)
    assert all(1 <= len(problema.random_state(rng)) <= 3 for _ in range(50))


def test_cli_imprime_la_comparacion(capsys):
    assert main(["--peso", "238"]) == 0
    salida = capsys.readouterr().out
    assert "BFS" in salida and "A*" in salida and "HC" in salida
