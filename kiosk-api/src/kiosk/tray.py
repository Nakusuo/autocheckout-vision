from typing import Protocol, runtime_checkable

from kiosk.catalog import Catalog
from kiosk.scale import SimulatedScale


@runtime_checkable
class Detector(Protocol):
    def detect(self) -> list[str]: ...


class SimulatedTray:
    """Bandeja simulada: hace de cámara (detector) y carga la balanza simulada."""

    def __init__(self, catalog: Catalog, scale: SimulatedScale):
        self._catalog = catalog
        self._scale = scale
        self._skus: list[str] = []

    def place(self, skus: list[str]) -> None:
        products = []
        for sku in skus:
            product = self._catalog.get(sku)
            if product is None:
                raise ValueError(f"Producto desconocido: {sku}")
            products.append(product)
        self._skus = list(skus)
        self._scale.set_load(sum(p.weight_g for p in products))

    def detect(self) -> list[str]:
        return list(self._skus)
