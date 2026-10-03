from collections import Counter
from dataclasses import dataclass

from kiosk.catalog import Catalog

TOLERANCE_G = 5.0


@dataclass(frozen=True)
class CartLine:
    sku: str
    name: str
    quantity: int
    unit_price_cents: int


@dataclass(frozen=True)
class Cart:
    lines: tuple[CartLine, ...]
    theoretical_weight_g: float
    total_cents: int
    unknown_skus: tuple[str, ...]

    @property
    def item_count(self) -> int:
        return sum(line.quantity for line in self.lines)


def build_cart(skus: list[str], catalog: Catalog) -> Cart:
    lines: list[CartLine] = []
    unknown: list[str] = []
    weight = 0.0
    total = 0
    for sku, qty in sorted(Counter(skus).items()):
        product = catalog.get(sku)
        if product is None:
            unknown.extend([sku] * qty)
            continue
        lines.append(CartLine(sku, product.name, qty, product.price_cents))
        weight += product.weight_g * qty
        total += product.price_cents * qty
    return Cart(tuple(lines), round(weight, 1), total, tuple(unknown))


@dataclass(frozen=True)
class WeightCheck:
    ok: bool
    diff_g: float


def check_weight(
    theoretical_g: float, measured_g: float, tolerance_g: float = TOLERANCE_G
) -> WeightCheck:
    diff = round(abs(measured_g - theoretical_g), 1)
    return WeightCheck(ok=diff <= tolerance_g, diff_g=diff)
