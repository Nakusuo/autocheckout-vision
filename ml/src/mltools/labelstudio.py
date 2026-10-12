"""Genera la configuración de etiquetado de Label Studio a partir del catálogo."""

import argparse
from collections.abc import Iterable
from pathlib import Path

# Solo se usa quoteattr para escapar; no se parsea XML.
from xml.sax.saxutils import quoteattr  # nosec B406

from mltools.catalog import REPO, load_skus
from mltools.console import utf8_output


def label_config(skus: Iterable[str]) -> str:
    labels = "\n".join(f"    <Label value={quoteattr(sku)}/>" for sku in sorted(skus))
    return (
        "<View>\n"
        '  <Image name="image" value="$image" zoom="true"/>\n'
        '  <RectangleLabels name="label" toName="image">\n'
        f"{labels}\n"
        "  </RectangleLabels>\n"
        "</View>\n"
    )


def main(argv: list[str] | None = None) -> int:
    utf8_output()
    parser = argparse.ArgumentParser(description="Configuración de Label Studio.")
    parser.add_argument("--catalog", type=Path, default=REPO / "catalog" / "products.csv")
    parser.add_argument("--out", type=Path, help="Archivo donde guardarla (si no, se imprime)")
    args = parser.parse_args(argv)
    config = label_config(load_skus(args.catalog))
    if args.out:
        args.out.write_text(config, encoding="utf-8")
        print(f"Configuración guardada en {args.out}")
    else:
        print(config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
