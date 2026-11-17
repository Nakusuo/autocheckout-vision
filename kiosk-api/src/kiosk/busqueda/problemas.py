"""Problemas concretos del quiosco modelados como espacios de estados.

1. `FlujoCompra`: las pantallas W1–W4 (estados de `kiosk.checkout.Checkout`).
   Las transiciones NO se copian: se obtienen ejecutando los métodos reales de `Checkout`, así que
   si cambia la máquina de estados, la búsqueda cambia con ella.
2. `PesoBandeja`: dado el peso medido en la balanza, ¿qué productos del catálogo hay en la bandeja?
   Es una búsqueda de subconjuntos (tipo «subset sum») con la tolerancia de ±5 g del SRS.
"""

import math
import random
from collections.abc import Iterable

from kiosk.busqueda.algoritmos import Action, State
from kiosk.catalog import Catalog, Product
from kiosk.checkout import MAX_ITEMS, Checkout, TransitionError
from kiosk.checkout import State as Screen
from kiosk.fusion import TOLERANCE_G, build_cart

# Producto ficticio: el flujo solo cuenta unidades, no importa cuál.
_PLACEHOLDER = Catalog([Product("X", "Producto", 100, 10.0)])

# Cota inferior de acciones que faltan hasta W4 desde cada pantalla (heurística admisible).
_STEPS_TO_PAID = {
    Screen.IDLE: 5,  # iniciar, agregar, confirmar, pagar, pago confirmado
    Screen.SCANNING: 3,  # (agregar si no hay nada), confirmar, pagar, pago confirmado
    Screen.CONFIRMING: 2,
    Screen.PAYING: 1,
    Screen.PAID: 0,
    Screen.OUT_OF_SERVICE: 6,
}


class FlujoCompra:
    """Estado = (pantalla, unidades en el carrito). Meta = pantalla W4 (pago confirmado)."""

    ACTIONS = (
        "iniciar",
        "agregar",
        "quitar",
        "confirmar",
        "corregir",
        "pagar",
        "pago_ok",
        "pago_vencido",
        "cancelar",
        "reiniciar",
        "falla",
        "recuperar",
    )

    def initial_state(self) -> State:
        return (Screen.IDLE, 0)

    def is_goal(self, state: State) -> bool:
        return state[0] is Screen.PAID

    def heuristic(self, state: State) -> float:
        screen, items = state
        extra = 1 if screen is Screen.SCANNING and items == 0 else 0
        return _STEPS_TO_PAID[screen] + extra

    @staticmethod
    def _checkout(state: State) -> Checkout:
        screen, items = state
        co = Checkout(require_weight=False)
        co.state = screen
        if items:
            co.cart = build_cart(["X"] * items, _PLACEHOLDER)
        return co

    def _apply(self, action: str, state: State) -> State:
        """Aplica la acción con el Checkout real; lanza TransitionError si no está permitida."""
        screen, items = state
        co = self._checkout(state)
        if action == "agregar":
            if screen is not Screen.SCANNING or items >= MAX_ITEMS + 1:
                raise TransitionError("no se puede agregar")
            items += 1
        elif action == "quitar":
            if screen is not Screen.SCANNING or items == 0:
                raise TransitionError("no se puede quitar")
            items -= 1
        else:
            getattr(co, _METHODS[action])()
            if action in {"cancelar", "reiniciar", "recuperar"}:
                items = 0
            return (co.state, items)
        return (screen, items)

    def successors(self, state: State) -> Iterable[tuple[Action, State, float]]:
        for action in self.ACTIONS:
            try:
                nxt = self._apply(action, state)
            except TransitionError:
                continue
            if nxt != state:
                yield action, nxt, 1.0


_METHODS = {
    "iniciar": "start",
    "confirmar": "confirm",
    "corregir": "correct",
    "pagar": "pay",
    "pago_ok": "payment_confirmed",
    "pago_vencido": "payment_timeout",
    "cancelar": "cancel",
    "reiniciar": "reset",
    "falla": "fault",
    "recuperar": "recover",
}


def alcanzables(problem: FlujoCompra) -> set[State]:
    """Todos los estados alcanzables desde el inicial (recorrido exhaustivo)."""
    seen = {problem.initial_state()}
    pending = [problem.initial_state()]
    while pending:
        for _, nxt, _ in problem.successors(pending.pop()):
            if nxt not in seen:
                seen.add(nxt)
                pending.append(nxt)
    return seen


def sin_salida(problem: FlujoCompra) -> set[State]:
    """Estados alcanzables desde los que ya no se puede volver al inicio (deberían ser ninguno)."""
    reach = alcanzables(problem)
    start = problem.initial_state()
    return {s for s in reach if not _llega(problem, s, start)}


def _llega(problem: FlujoCompra, origin: State, target: State) -> bool:
    seen, pending = {origin}, [origin]
    while pending:
        cur = pending.pop()
        if cur == target:
            return True
        for _, nxt, _ in problem.successors(cur):
            if nxt not in seen:
                seen.add(nxt)
                pending.append(nxt)
    return False


class PesoBandeja:
    """Estado = SKUs elegidos (en orden canónico para no repetir permutaciones).

    Coste de cada paso: 1 producto. La meta es que el peso teórico quede a ±`tolerance_g` del
    medido, por lo que la solución óptima es la que usa menos productos.
    """

    def __init__(
        self,
        catalog: Catalog,
        measured_g: float,
        tolerance_g: float = TOLERANCE_G,
        max_items: int = MAX_ITEMS,
    ) -> None:
        self._products = sorted(catalog.all(), key=lambda p: p.sku)
        self._weights = {p.sku: p.weight_g for p in self._products}
        self._max_w = max(self._weights.values())
        self.measured_g = measured_g
        self.tolerance_g = tolerance_g
        self.max_items = max_items

    def weight(self, state: State) -> float:
        return sum(self._weights[s] for s in state)

    def initial_state(self) -> State:
        return ()

    def is_goal(self, state: State) -> bool:
        return bool(state) and abs(self.weight(state) - self.measured_g) <= self.tolerance_g

    def successors(self, state: State) -> Iterable[tuple[Action, State, float]]:
        if len(state) >= self.max_items:
            return
        last = state[-1] if state else ""
        for p in self._products:
            if p.sku >= last:
                yield p.sku, (*state, p.sku), 1.0

    def heuristic(self, state: State) -> float:
        """Admisible: faltan al menos ⌈(peso restante − tolerancia) / peso máximo⌉ productos.

        Si ya se pasó del peso medido más la tolerancia, no hay solución: coste infinito.
        """
        remaining = self.measured_g - self.weight(state)
        if remaining < -self.tolerance_g:
            return math.inf
        if remaining <= self.tolerance_g:
            return 0.0 if state else 1.0
        return float(math.ceil((remaining - self.tolerance_g) / self._max_w))

    # --- Búsqueda local: el estado es una combinación completa y se mueve un producto a la vez ---

    def score(self, state: State) -> float:
        """Cuanto más cerca del peso medido, mejor (máximo 0)."""
        return -abs(self.weight(state) - self.measured_g)

    def neighbors(self, state: State) -> Iterable[State]:
        """Vecinos: cambiar un producto por otro, agregar uno o quitar uno."""
        skus = [p.sku for p in self._products]
        for i in range(len(state)):
            for sku in skus:
                if sku != state[i]:
                    yield tuple(sorted((*state[:i], sku, *state[i + 1 :])))
            if len(state) > 1:
                yield (*state[:i], *state[i + 1 :])
        if len(state) < self.max_items:
            for sku in skus:
                yield tuple(sorted((*state, sku)))

    def random_state(self, rng: random.Random) -> State:
        n = rng.randint(1, self.max_items)
        return tuple(sorted(rng.choice(self._products).sku for _ in range(n)))
