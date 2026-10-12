from pathlib import Path

import pytest

from mltools.importar import import_dataset, sku_from_folder


@pytest.mark.parametrize(
    ("folder", "sku"),
    [
        ("CANCUN-33", "CANCUN-33"),
        ("Glacitas-30g", "GLACITAS-30G"),
        ("KRpiña-3,03L", "KRPINA-3.03L"),
        ("Club Social 24", "CLUB-SOCIAL-24"),
    ],
)
def test_sku_from_folder(folder, sku):
    assert sku_from_folder(folder) == sku


def put(root: Path, rel: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")


def test_import_copies_photos_and_skips_extras(tmp_path):
    src, out = tmp_path / "drive", tmp_path / "raw"
    put(src, "Glacitas-30g/AR_glacitas_001.jpeg")
    put(src, "Glacitas-30g/nota.txt")
    put(src, "videos/JP_takis.mp4")
    put(src, "_sobran/AGUA-625/a.jpg")
    (src / "COCACOLA-500").mkdir()
    put(src, "catalogo.xlsx")

    counts = import_dataset(src, out)

    assert counts == {"GLACITAS-30G": 1, "videos": 1}
    assert (out / "GLACITAS-30G" / "AR_glacitas_001.jpeg").exists()
    assert not (out / "GLACITAS-30G" / "nota.txt").exists()
    assert not (out / "COCACOLA-500").exists()
