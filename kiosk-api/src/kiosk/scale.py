import random
from typing import Protocol, runtime_checkable


@runtime_checkable
class ScaleReader(Protocol):
    def read(self) -> float: ...


class SimulatedScale:
    """Balanza falsa: peso cargado ± ruido, más un desvío opcional («modo trampa»)."""

    def __init__(self, noise_g: float = 2.0, seed: int | None = None):
        self._rng = random.Random(seed)  # nosec B311 — simulación, no criptografía
        self._noise = noise_g
        self._load = 0.0
        self._offset = 0.0

    def set_load(self, grams: float) -> None:
        self._load = grams

    def set_trap(self, offset_g: float) -> None:
        self._offset = offset_g

    def read(self) -> float:
        grams = self._load + self._offset + self._rng.uniform(-self._noise, self._noise)
        return round(max(grams, 0.0), 1)
