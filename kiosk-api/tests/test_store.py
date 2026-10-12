from pathlib import Path

from kiosk.catalog import Product
from kiosk.store import init_db, load_catalog


def write_seed(path: Path, price: int) -> Path:
    path.write_text(
        f"sku,name,price_cents,weight_g\nAGUA,Agua,{price},651.0\n", encoding="utf-8"
    )
    return path


def test_init_and_load_roundtrip(tmp_path: Path):
    db = tmp_path / "kiosk.db"
    init_db(db, write_seed(tmp_path / "seed.csv", 250))

    assert load_catalog(db).get("AGUA") == Product("AGUA", "Agua", 250, 651.0)


def test_init_twice_updates_without_duplicates(tmp_path: Path):
    db = tmp_path / "kiosk.db"
    init_db(db, write_seed(tmp_path / "seed.csv", 250))
    init_db(db, write_seed(tmp_path / "seed.csv", 300))

    catalog = load_catalog(db)
    assert len(catalog.all()) == 1
    assert catalog.get("AGUA").price_cents == 300


def test_init_removes_products_no_longer_in_seed(tmp_path: Path):
    db = tmp_path / "kiosk.db"
    seed = tmp_path / "seed.csv"
    seed.write_text(
        "sku,name,price_cents,weight_g\nAGUA,Agua,250,651.0\nCOLA,Cola,350,528.0\n",
        encoding="utf-8",
    )
    init_db(db, seed)
    init_db(db, write_seed(seed, 250))

    assert [p.sku for p in load_catalog(db).all()] == ["AGUA"]
