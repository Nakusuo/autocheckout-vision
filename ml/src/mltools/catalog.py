import csv
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]


def load_skus(catalog_csv: Path) -> set[str]:
    with catalog_csv.open(encoding="utf-8", newline="") as f:
        return {row["sku"] for row in csv.DictReader(f)}
