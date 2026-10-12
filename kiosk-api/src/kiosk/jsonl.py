"""Logs JSONL que no crecen sin límite: al pasar `MAX_BYTES` el archivo se rota a `<nombre>.1.jsonl`.

Se guardan como mucho dos archivos (el actual y uno anterior), unos 10 MB en total.
"""

import json
from pathlib import Path

MAX_BYTES = 5 * 1024 * 1024
KEEP_IN_MEMORY = 1000


def backup_of(path: Path) -> Path:
    return path.with_name(f"{path.stem}.1{path.suffix}")


def append(path: Path, row: dict, max_bytes: int | None = None) -> None:
    limit = MAX_BYTES if max_bytes is None else max_bytes
    if path.exists() and path.stat().st_size >= limit:
        path.replace(backup_of(path))
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_rows(path: Path) -> list[dict]:
    """Filas del archivo anterior y del actual, en orden."""
    rows: list[dict] = []
    for p in (backup_of(path), path):
        if p.exists():
            rows += [
                json.loads(line)
                for line in p.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
    return rows
