"""Arma el dataset YOLO (train/val/test + data.yaml) desde la exportación de Label Studio."""

import argparse
import hashlib
import shutil
from pathlib import Path

from mltools.catalog import REPO, load_skus

IMAGE_EXT = {".jpg", ".jpeg", ".png"}
RATIOS = (0.7, 0.2, 0.1)
SPLITS = ("train", "val", "test")


def split_names(names: list[str], ratios=RATIOS, seed: int = 42) -> dict[str, list[str]]:
    ordered = sorted(names, key=lambda n: hashlib.sha256(f"{seed}:{n}".encode()).hexdigest())
    n_train = round(len(ordered) * ratios[0])
    n_val = round(len(ordered) * ratios[1])
    return {
        "train": sorted(ordered[:n_train]),
        "val": sorted(ordered[n_train : n_train + n_val]),
        "test": sorted(ordered[n_train + n_val :]),
    }


def read_classes(export_dir: Path) -> list[str]:
    path = export_dir / "classes.txt"
    if not path.exists():
        raise ValueError("Falta classes.txt en la exportación de Label Studio")
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _check_label(path: Path, n_classes: int) -> None:
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        parts = line.split()
        try:
            cls = int(parts[0])
            coords = [float(v) for v in parts[1:]]
        except (ValueError, IndexError):
            cls, coords = -1, []
        if len(coords) != 4 or not 0 <= cls < n_classes or not all(0 <= v <= 1 for v in coords):
            raise ValueError(f"etiqueta inválida en {path.name}, línea {number}: {line!r}")


def _prepare_output(out_dir: Path) -> None:
    if out_dir.exists() and any(out_dir.iterdir()):
        if not (out_dir / "data.yaml").exists():
            raise ValueError(f"La carpeta {out_dir} no fue generada por split; elige otra salida")
        shutil.rmtree(out_dir)
    for kind in ("images", "labels"):
        for split in SPLITS:
            (out_dir / kind / split).mkdir(parents=True, exist_ok=True)


def build_dataset(export_dir: Path, out_dir: Path, skus: set[str], seed: int = 42) -> Path:
    classes = read_classes(export_dir)
    unknown = sorted(set(classes) - skus)
    if unknown:
        raise ValueError(f"Clases que no están en el catálogo: {', '.join(unknown)}")
    images = {
        p.stem: p for p in (export_dir / "images").iterdir() if p.suffix.lower() in IMAGE_EXT
    }
    labels_dir = export_dir / "labels"
    missing = sorted(stem for stem in images if not (labels_dir / f"{stem}.txt").exists())
    if missing:
        raise ValueError(f"{len(missing)} foto(s) sin etiquetas, por ejemplo {missing[0]}")
    for stem in images:
        _check_label(labels_dir / f"{stem}.txt", len(classes))

    _prepare_output(out_dir)
    for split, stems in split_names(list(images), seed=seed).items():
        for stem in stems:
            shutil.copy2(images[stem], out_dir / "images" / split / images[stem].name)
            shutil.copy2(labels_dir / f"{stem}.txt", out_dir / "labels" / split / f"{stem}.txt")

    names = "\n".join(f"  {i}: {name}" for i, name in enumerate(classes))
    yaml = out_dir / "data.yaml"
    yaml.write_text(
        f"path: {out_dir.resolve().as_posix()}\n"
        "train: images/train\nval: images/val\ntest: images/test\n"
        f"names:\n{names}\n",
        encoding="utf-8",
    )
    return yaml


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Arma el dataset YOLO desde Label Studio.")
    parser.add_argument("export_dir", type=Path, nargs="?", default=REPO / "ml" / "data" / "labeled")
    parser.add_argument("--out", type=Path, default=REPO / "ml" / "data" / "dataset")
    parser.add_argument("--catalog", type=Path, default=REPO / "catalog" / "products.csv")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)
    try:
        yaml = build_dataset(args.export_dir, args.out, load_skus(args.catalog), args.seed)
    except (ValueError, FileNotFoundError) as e:
        print(f"❌ {e}")
        return 1
    for split in SPLITS:
        print(f"{split}: {len(list((args.out / 'images' / split).iterdir()))} fotos")
    print(f"Listo: {yaml}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
