"""Revisa la carpeta del dataset descargada del Drive antes de etiquetar."""

import argparse
import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from mltools.catalog import REPO, load_skus

IMAGE_EXT = {".jpg", ".jpeg", ".png"}
VIDEO_EXT = {".mp4", ".mov", ".avi"}
SPECIAL = {"mezclas", "videos"}
IGNORED = {"desktop.ini", "thumbs.db", ".ds_store"}
MIN_PER_PRODUCT = 100


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass
class Report:
    counts: dict[str, int] = field(default_factory=dict)
    unknown_folders: list[str] = field(default_factory=list)
    missing_skus: list[str] = field(default_factory=list)
    low_skus: list[str] = field(default_factory=list)
    bad_files: list[str] = field(default_factory=list)
    duplicates: list[tuple[str, str]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not (self.unknown_folders or self.bad_files)


def check_dataset(root: Path, skus: set[str], min_per_product: int = MIN_PER_PRODUCT) -> Report:
    report = Report()
    seen: dict[str, str] = {}
    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        name = folder.name
        if name not in skus and name not in SPECIAL:
            report.unknown_folders.append(name)
            continue
        allowed = VIDEO_EXT if name == "videos" else IMAGE_EXT
        count = 0
        for path in sorted(folder.rglob("*")):
            if not path.is_file() or path.name.lower() in IGNORED:
                continue
            rel = path.relative_to(root).as_posix()
            if path.suffix.lower() not in allowed:
                report.bad_files.append(rel)
                continue
            digest = _sha256(path)
            if digest in seen:
                report.duplicates.append((seen[digest], rel))
                continue
            seen[digest] = rel
            count += 1
        report.counts[name] = count
    report.missing_skus = sorted(skus - report.counts.keys())
    report.low_skus = sorted(
        s for s in skus if s in report.counts and report.counts[s] < min_per_product
    )
    return report


def format_report(report: Report) -> str:
    lines = ["Producto | Fotos | Estado", "--- | --- | ---"]
    for name in sorted(set(report.counts) | set(report.missing_skus)):
        if name in report.missing_skus:
            state = "❌ falta la carpeta"
        elif name in report.low_skus:
            state = "⚠️ pocas fotos"
        else:
            state = "✅"
        lines.append(f"{name} | {report.counts.get(name, 0)} | {state}")
    if report.unknown_folders:
        lines.append("\n❌ Carpetas que no están en el catálogo (renómbralas o bórralas):")
        lines += [f"  - {name}" for name in report.unknown_folders]
    if report.bad_files:
        lines.append("\n❌ Archivos con formato no permitido:")
        lines += [f"  - {rel}" for rel in report.bad_files]
    if report.duplicates:
        lines.append(f"\n⚠️ {len(report.duplicates)} foto(s) repetida(s) (se cuentan una vez):")
        lines += [f"  - {b} = {a}" for a, b in report.duplicates[:10]]
    lines.append("\nResultado: " + ("OK" if report.ok else "HAY QUE CORREGIR"))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Revisa la carpeta del dataset.")
    parser.add_argument("root", type=Path, nargs="?", default=REPO / "ml" / "data" / "raw")
    parser.add_argument("--catalog", type=Path, default=REPO / "catalog" / "products.csv")
    parser.add_argument("--min", type=int, default=MIN_PER_PRODUCT, dest="min_per_product")
    args = parser.parse_args(argv)
    if not args.root.is_dir():
        print(f"No existe la carpeta {args.root}. Descarga ahí el Drive AutoCaja-dataset.")
        return 1
    report = check_dataset(args.root, load_skus(args.catalog), args.min_per_product)
    print(format_report(report))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
