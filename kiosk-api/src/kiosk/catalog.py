import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Product:
    sku: str
    name: str
    price_cents: int
    weight_g: float


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
