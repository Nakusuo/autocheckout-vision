from pathlib import Path

import pytest

from kiosk.catalog import Catalog, Product


def test_from_csv_loads_products(tmp_path: Path):
    csv_file = tmp_path / "products.csv"
    csv_file.write_text(
        "sku,name,price_cents,weight_g\nAGUA-625,Agua 625 ml,250,651.0\n", encoding="utf-8"
    )

    catalog = Catalog.from_csv(csv_file)

    assert catalog.get("AGUA-625") == Product("AGUA-625", "Agua 625 ml", 250, 651.0)


def test_get_unknown_sku_returns_none():
    assert Catalog([]).get("NO-EXISTE") is None


def test_repo_seed_catalog_loads():
    seed = Path(__file__).resolve().parents[2] / "catalog" / "products.csv"
    catalog = Catalog.from_csv(seed)
    assert catalog.get("CANCUN-33") is not None


@pytest.mark.parametrize(
    ("sku", "name", "price", "weight", "msg"),
    [
        ("", "Agua", 100, 10.0, "SKU"),
        ("A", "Agua", -1, 10.0, "negativo"),
        ("A", "Agua", 100, 0.0, "peso"),
    ],
)
def test_invalid_products_are_rejected(sku, name, price, weight, msg):
    with pytest.raises(ValueError, match=msg):
        Product(sku, name, price, weight)
