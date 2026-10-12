"""Copia la carpeta del Drive (AutoCaja-dataset) a ml/data/raw con nombres de SKU limpios.

- Cada carpeta de producto pasa a su SKU: «KRpiña-3,03L» → «KRPINA-3.03L».
- Las fotos .heic del iPhone se convierten a .jpg (requiere el extra `heic`).
- Se saltan las carpetas que empiezan con «_» (por ejemplo, _sobran) y las vacías.

Uso: python -m mltools.importar RUTA/AutoCaja-dataset [--out data/raw]
"""

import argparse
import re
import shutil
import unicodedata
from pathlib import Path

from mltools.catalog import REPO
from mltools.console import utf8_output

PHOTO_EXT = {".jpg", ".jpeg", ".png"}
HEIC_EXT = {".heic", ".heif"}
VIDEO_EXT = {".mp4", ".mov", ".avi"}
SPECIAL = {"mezclas", "videos"}


def sku_from_folder(name: str) -> str:
    """Mayúsculas, sin tildes ni eñes, coma decimal como punto y guiones entre palabras."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    ascii_name = ascii_name.replace(",", ".").upper()
    return re.sub(r"[^A-Z0-9.]+", "-", ascii_name).strip("-")


def _heic_to_jpg(src: Path, dst: Path) -> None:
    try:
        import pillow_heif
        from PIL import Image
    except ImportError as e:  # pragma: no cover - depende del entorno
        raise SystemExit('Para fotos .heic instala el extra: pip install -e ".[heic]"') from e
    pillow_heif.register_heif_opener()
    with Image.open(src) as im:
        im.convert("RGB").save(dst, "JPEG", quality=92)


def import_dataset(src: Path, out: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    for folder in sorted(p for p in src.iterdir() if p.is_dir() and not p.name.startswith("_")):
        name = folder.name if folder.name in SPECIAL else sku_from_folder(folder.name)
        allowed = VIDEO_EXT if name == "videos" else PHOTO_EXT | HEIC_EXT
        files = [f for f in sorted(folder.iterdir()) if f.is_file() and f.suffix.lower() in allowed]
        if not files:
            continue
        dest = out / name
        dest.mkdir(parents=True, exist_ok=True)
        for f in files:
            if f.suffix.lower() in HEIC_EXT:
                _heic_to_jpg(f, dest / f"{f.stem}.jpg")
            else:
                shutil.copy2(f, dest / f.name)
        counts[name] = len(files)
    return counts


def main(argv: list[str] | None = None) -> int:
    utf8_output()
    parser = argparse.ArgumentParser(description="Importa el dataset del Drive a ml/data/raw.")
    parser.add_argument("src", type=Path)
    parser.add_argument("--out", type=Path, default=REPO / "ml" / "data" / "raw")
    args = parser.parse_args(argv)
    if not args.src.is_dir():
        print(f"No existe la carpeta {args.src}")
        return 1
    counts = import_dataset(args.src, args.out)
    for name, n in counts.items():
        print(f"{name:20s} {n:4d}")
    print(f"Total: {sum(counts.values())} archivos en {len(counts)} carpetas → {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
