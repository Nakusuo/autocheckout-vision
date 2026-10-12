import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Product:
    sku: str
    name: str
    price_cents: int
    weight_g: float

    def __post_init__(self):
        # Mismas reglas que la tabla SQLite (store.SCHEMA), también al leer el CSV directamente.
        if not self.sku or not self.name:
            raise ValueError("Producto sin SKU o sin nombre")
        if self.price_cents < 0:
            raise ValueError(f"{self.sku}: precio negativo")
        if self.weight_g <= 0:
            raise ValueError(f"{self.sku}: el peso debe ser mayor que 0")


class Catalog:
    def __init__(self, products: list[Product]):
        self._by_sku = {p.sku: p for p in products}

    @classmethod
    def from_csv(cls, path: Path) -> "Catalog":
        with path.open(encoding="utf-8", newline="") as f:
            return cls(
                [
                    Product(r["sku"], r["name"], int(r["price_cents"]), float(r["weight_g"]))
                    for r in csv.DictReader(f)
                ]
            )

    def get(self, sku: str) -> Product | None:
        return self._by_sku.get(sku)

    def all(self) -> list[Product]:
        return list(self._by_sku.values())
