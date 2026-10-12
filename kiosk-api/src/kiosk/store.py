import sqlite3
from contextlib import closing
from pathlib import Path

from kiosk.catalog import Catalog, Product

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    sku TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    price_cents INTEGER NOT NULL CHECK (price_cents >= 0),
    weight_g REAL NOT NULL CHECK (weight_g > 0)
)
"""


def init_db(db_path: Path, seed_csv: Path) -> None:
    rows = [
        (p.sku, p.name, p.price_cents, p.weight_g) for p in Catalog.from_csv(seed_csv).all()
    ]
    with closing(sqlite3.connect(db_path)) as conn, conn:
        conn.execute(SCHEMA)
        # El CSV manda: los productos que ya no están se borran (en la misma transacción).
        conn.execute("DELETE FROM products")
        conn.executemany("INSERT INTO products VALUES (?, ?, ?, ?)", rows)


def load_catalog(db_path: Path) -> Catalog:
    with closing(sqlite3.connect(db_path)) as conn:
        rows = conn.execute("SELECT sku, name, price_cents, weight_g FROM products").fetchall()
    return Catalog([Product(*row) for row in rows])
