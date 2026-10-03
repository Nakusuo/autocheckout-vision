from kiosk.catalog import Catalog, Product
from kiosk.fusion import build_cart, check_weight

CATALOG = Catalog(
    [
        Product("AGUA", "Agua", 250, 651.0),
        Product("CHOCO", "Chocolate", 280, 33.0),
    ]
)


def test_build_cart_groups_quantities_and_sums():
    cart = build_cart(["AGUA", "CHOCO", "CHOCO"], CATALOG)

    assert [(line.sku, line.quantity) for line in cart.lines] == [("AGUA", 1), ("CHOCO", 2)]
    assert cart.item_count == 3
    assert cart.total_cents == 250 + 2 * 280
    assert cart.theoretical_weight_g == 651.0 + 2 * 33.0
    assert cart.unknown_skus == ()


def test_build_cart_reports_unknown_skus():
    cart = build_cart(["AGUA", "FANTASMA"], CATALOG)

    assert cart.item_count == 1
    assert cart.unknown_skus == ("FANTASMA",)


def test_weight_within_tolerance_is_ok():
    assert check_weight(717.0, 720.0).ok is True


def test_weight_exactly_at_limit_is_ok():
    result = check_weight(100.0, 105.0)
    assert result.ok is True
    assert result.diff_g == 5.0


def test_weight_over_limit_blocks():
    result = check_weight(100.0, 105.1)
    assert result.ok is False
    assert result.diff_g == 5.1


def test_lighter_tray_also_blocks():
    assert check_weight(684.0, 651.0).ok is False
