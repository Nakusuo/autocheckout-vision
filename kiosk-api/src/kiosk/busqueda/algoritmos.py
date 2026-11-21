"""Algoritmos de búsqueda sobre un espacio de estados.

Un problema se modela formalmente con cinco elementos (Russell & Norvig):
estado inicial, acciones aplicables, modelo de transición, prueba de meta y coste de camino.

- No informados: BFS (amplitud) y DFS (profundidad). No usan conocimiento del dominio.
- Informado: A* ordena la frontera por f(n) = g(n) + h(n). Con h admisible es óptimo.
- Búsqueda local: Hill Climbing (ascenso de colina) sobre una función objetivo; no guarda
  caminos, solo el estado actual, y puede quedar atrapado en máximos locales.

Todos devuelven las mismas métricas (nodos expandidos, generados y frontera máxima) para
poder compararlos con números y no solo con teoría.
"""

import heapq
import itertools
import random
from collections import deque
from collections.abc import Callable, Hashable, Iterable
from dataclasses import dataclass
from typing import Any, Protocol

Action = Hashable
State = Any  # cada problema usa su propio tipo de estado (hashable)


class Problem(Protocol):
    """Espacio de estados: lo mínimo que necesita un algoritmo de búsqueda."""

    def initial_state(self) -> State: ...

    def successors(self, state: State) -> Iterable[tuple[Action, State, float]]:
        """Pares (acción, estado siguiente, coste del paso)."""
        ...

    def is_goal(self, state: State) -> bool: ...


class InformedProblem(Problem, Protocol):
    def heuristic(self, state: State) -> float:
        """Estimación del coste restante hasta la meta (h(n))."""
        ...


@dataclass(frozen=True)
class SearchResult:
    found: bool
    actions: tuple[Action, ...]
    cost: float
    expanded: int  # nodos sacados de la frontera y desarrollados
    generated: int  # nodos creados
    max_frontier: int  # memoria: tamaño máximo de la frontera


def _rebuild(parents: dict[State, tuple[State, Action] | None], goal: State) -> tuple[Action, ...]:
    actions: list[Action] = []
    node: State = goal
    while (link := parents[node]) is not None:
        node, action = link
        actions.append(action)
    return tuple(reversed(actions))


def bfs(problem: Problem) -> SearchResult:
    """Amplitud: expande por niveles. Completa; óptima si todos los pasos cuestan lo mismo."""
    start = problem.initial_state()
    if problem.is_goal(start):
        return SearchResult(True, (), 0.0, 0, 1, 1)
    parents: dict[State, tuple[State, Action] | None] = {start: None}
    costs: dict[State, float] = {start: 0.0}
    frontier: deque[State] = deque([start])
    expanded, generated, peak = 0, 1, 1
    while frontier:
        state = frontier.popleft()
        expanded += 1
        for action, nxt, step in problem.successors(state):
            if nxt in parents:
                continue
            parents[nxt] = (state, action)
            costs[nxt] = costs[state] + step
            generated += 1
            if problem.is_goal(nxt):
                return SearchResult(True, _rebuild(parents, nxt), costs[nxt], expanded, generated, peak)
            frontier.append(nxt)
        peak = max(peak, len(frontier))
    return SearchResult(False, (), 0.0, expanded, generated, peak)


def dfs(problem: Problem, depth_limit: int | None = None) -> SearchResult:
    """Profundidad con control de ciclos. Poca memoria, pero no garantiza el camino más corto.

    `depth_limit` evita caminos infinitos (DFS limitado).
    """
    start = problem.initial_state()
    parents: dict[State, tuple[State, Action] | None] = {start: None}
    costs: dict[State, float] = {start: 0.0}
    depth: dict[State, int] = {start: 0}
    stack: list[State] = [start]
    expanded, generated, peak = 0, 1, 1
    while stack:
        state = stack.pop()
        if problem.is_goal(state):
            return SearchResult(True, _rebuild(parents, state), costs[state], expanded, generated, peak)
        expanded += 1
        if depth_limit is not None and depth[state] >= depth_limit:
            continue
        # Se apilan en orden inverso para explorar primero la primera acción.
        for action, nxt, step in reversed(list(problem.successors(state))):
            if nxt in parents:
                continue
            parents[nxt] = (state, action)
            costs[nxt] = costs[state] + step
            depth[nxt] = depth[state] + 1
            generated += 1
            stack.append(nxt)
        peak = max(peak, len(stack))
    return SearchResult(False, (), 0.0, expanded, generated, peak)


def a_star(problem: InformedProblem) -> SearchResult:
    """A*: f(n) = g(n) + h(n). Óptimo si h es admisible (nunca sobrestima) y consistente."""
    start = problem.initial_state()
    tie = itertools.count()  # desempata sin comparar estados
    g: dict[State, float] = {start: 0.0}
    parents: dict[State, tuple[State, Action] | None] = {start: None}
    frontier: list[tuple[float, int, State]] = [(problem.heuristic(start), next(tie), start)]
    closed: set[State] = set()
    expanded, generated, peak = 0, 1, 1
    while frontier:
        _, _, state = heapq.heappop(frontier)
        if state in closed:
            continue
        if problem.is_goal(state):
            return SearchResult(True, _rebuild(parents, state), g[state], expanded, generated, peak)
        closed.add(state)
        expanded += 1
        for action, nxt, step in problem.successors(state):
            new_g = g[state] + step
            if nxt in closed or new_g >= g.get(nxt, float("inf")):
                continue
            h = problem.heuristic(nxt)
            if h == float("inf"):  # callejón sin salida demostrado: se poda
                continue
            g[nxt] = new_g
            parents[nxt] = (state, action)
            generated += 1
            heapq.heappush(frontier, (new_g + h, next(tie), nxt))
        peak = max(peak, len(frontier))
    return SearchResult(False, (), 0.0, expanded, generated, peak)


@dataclass(frozen=True)
class LocalResult:
    state: State
    score: float
    steps: int  # movimientos aceptados
    evaluations: int  # veces que se evaluó la función objetivo


def hill_climbing(
    start: State,
    neighbors: Callable[[State], Iterable[State]],
    score: Callable[[State], float],
    max_steps: int = 1000,
) -> LocalResult:
    """Ascenso de colina por la máxima pendiente: pasa al mejor vecino mientras mejore.

    Se detiene en un óptimo local (ningún vecino mejora) o al agotar `max_steps`.
    """
    current, current_score = start, score(start)
    steps, evaluations = 0, 1
    while steps < max_steps:
        best, best_score = None, current_score
        for cand in neighbors(current):
            evaluations += 1
            s = score(cand)
            if s > best_score:
                best, best_score = cand, s
        if best is None:
            break
        current, current_score = best, best_score
        steps += 1
    return LocalResult(current, current_score, steps, evaluations)


def hill_climbing_restarts(
    random_start: Callable[[random.Random], State],
    neighbors: Callable[[State], Iterable[State]],
    score: Callable[[State], float],
    restarts: int = 10,
    seed: int = 0,
    max_steps: int = 1000,
) -> LocalResult:
    """Reinicio aleatorio: repite el ascenso desde puntos distintos para escapar de óptimos locales."""
    rng = random.Random(seed)  # nosec B311: reproducibilidad, no criptografía
    best = hill_climbing(random_start(rng), neighbors, score, max_steps)
    total_eval = best.evaluations
    for _ in range(max(1, restarts) - 1):
        res = hill_climbing(random_start(rng), neighbors, score, max_steps)
        total_eval += res.evaluations
        if res.score > best.score:
            best = res
    return LocalResult(best.state, best.score, best.steps, total_eval)
