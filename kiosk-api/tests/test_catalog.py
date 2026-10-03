from pathlib import Path

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
    assert catalog.get("GASEOSA-500") is not None
