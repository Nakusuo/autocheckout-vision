import time
from collections.abc import Callable
from typing import Protocol, runtime_checkable

from kiosk.catalog import Catalog
from kiosk.scale import SimulatedScale


@runtime_checkable
class Detector(Protocol):
    def detect(self) -> list[str]: ...


class SimulatedTray:
    """Bandeja simulada: hace de cámara (detector) y carga la balanza simulada.

    - `scan(sku)`: el producto pasa frente a la cámara unos segundos y queda en la bandeja.
    - `sneak(sku)`: queda en la bandeja sin pasar por la cámara (la cámara no lo vio).
    - `take(sku)`: se retira de la bandeja.
    - `place(skus, hidden)`: fija de golpe lo que ve la cámara y lo que pesa la bandeja
      (`hidden` pesa pero no se ve); lo usan las pruebas.
    """

    def __init__(
        self,
        catalog: Catalog,
        scale: SimulatedScale,
        clock: Callable[[], float] = time.monotonic,
        show_s: float = 1.5,
    ):
        self._catalog = catalog
        self._scale = scale
        self._clock = clock
        self._show_s = show_s
        self._tray: list[str] = []
        self._view: list[str] = []
        self._shows: list[tuple[str, float]] = []

    def _check(self, skus: list[str]) -> None:
        for sku in skus:
            if self._catalog.get(sku) is None:
                raise ValueError(f"Producto desconocido: {sku}")

    def _load(self) -> None:
        self._scale.set_load(sum(self._catalog.get(sku).weight_g for sku in self._tray))

    def place(self, skus: list[str], hidden: list[str] | None = None) -> None:
        hidden = hidden or []
        self._check([*skus, *hidden])
        self._view = list(skus)
        self._shows = []
        self._tray = [*skus, *hidden]
        self._load()

    def scan(self, sku: str) -> None:
        self._check([sku])
        self._shows.append((sku, self._clock() + self._show_s))
        self._tray.append(sku)
        self._load()

    def sneak(self, sku: str) -> None:
        self._check([sku])
        self._tray.append(sku)
        self._load()

    def take(self, sku: str) -> None:
        if sku not in self._tray:
            raise ValueError(f"No hay {sku} en la bandeja")
        self._tray.remove(sku)
        if sku in self._view:
            self._view.remove(sku)
        self._load()

    def contents(self) -> list[str]:
        return sorted(self._tray)

    def detect(self) -> list[str]:
        now = self._clock()
        self._shows = [(sku, until) for sku, until in self._shows if until > now]
        return [*self._view, *(sku for sku, _ in self._shows)]
