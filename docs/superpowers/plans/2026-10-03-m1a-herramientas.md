# M1 parte A — Herramientas del dataset y benchmark: plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Objetivo:** tener listas, antes de que lleguen las fotos, las herramientas para revisar el dataset del Drive, sacar cuadros de los videos, configurar Label Studio y medir la latencia de inferencia del RNF-01 (≤150 ms).

**Arquitectura:** nuevo paquete Python `mltools` en `ml/`, independiente de `kiosk-api`. Lee el catálogo directamente de `catalog/products.csv`. Cada herramienta es un módulo con una función pura que se prueba y un `main()` que la ejecuta desde la consola (`python -m mltools.<modulo>`). onnxruntime es opcional (extra `bench`) y solo lo importa el comando de benchmark.

**Stack:** Python 3.12, numpy, opencv-python-headless, onnxruntime (opcional), pytest.

**Spec:** [`docs/superpowers/specs/2026-10-03-autocheckout-design.md`](../specs/2026-10-03-autocheckout-design.md) · Hoja de ruta: M1

## Restricciones globales

- Los nombres de carpeta del dataset son **exactamente** los `sku` de `catalog/products.csv`, más las especiales `mezclas` y `videos`.
- Fotos válidas: `.jpg`, `.jpeg` y `.png`. Videos válidos (solo en `videos/`): `.mp4`, `.mov` y `.avi`. Se ignoran `desktop.ini`, `thumbs.db` y `.ds_store`, sin distinguir mayúsculas.
- Mínimo recomendado: **100 fotos por producto** (es un aviso, no un error).
- Errores que hacen fallar la revisión (código de salida 1): carpetas desconocidas o archivos con extensión inválida.
- RNF-01: **p95 ≤ 150 ms** por imagen, contando el preprocesamiento y la inferencia.
- Preprocesamiento YOLO: letterbox a 640 con relleno gris 114, BGR→RGB, CHW, float32 en [0,1] y batch 1.
- Los datos no van a git: todo `ml/data/` queda ignorado.
- Textos para el usuario en español. Ramas cortas por tarea, unidas con `--no-ff` a `feature/m1-herramientas`, sin Co-Authored-By.

## Estructura de archivos

```
ml/
  pyproject.toml
  src/mltools/__init__.py
  src/mltools/catalog.py         # load_skus
  src/mltools/dataset_check.py   # check_dataset, format_report, main
  src/mltools/frames.py          # extract_frames, main
  src/mltools/labelstudio.py     # label_config, main
  src/mltools/bench.py           # Stats, measure, letterbox, main
  tests/test_dataset_check.py, test_frames.py, test_labelstudio.py, test_bench.py
docs/ml/etiquetado.md            # guía de Label Studio para el equipo
.gitignore                       # ml/data/raw/ → ml/data/
.github/workflows/ci.yml         # + job ml
README.md                        # + sección herramientas del dataset
```

---

### Task 1: paquete mltools y verificador del dataset

**Files:**
- Create: `ml/pyproject.toml`, `ml/src/mltools/__init__.py`, `ml/src/mltools/catalog.py`, `ml/src/mltools/dataset_check.py`
- Modify: `.gitignore` (la línea `ml/data/raw/` pasa a `ml/data/`)
- Test: `ml/tests/test_dataset_check.py`

**Interfaces:**
- Produce: `load_skus(catalog_csv: Path) -> set[str]`, `REPO: Path` (en `catalog.py`, es la raíz del repo), `Report` (con `counts: dict[str,int]`, `unknown_folders`, `missing_skus`, `low_skus`, `bad_files: list[str]`, `duplicates: list[tuple[str,str]]` y la propiedad `ok`), `check_dataset(root: Path, skus: set[str], min_per_product: int = 100) -> Report`, `format_report(report: Report) -> str`, `main(argv: list[str] | None = None) -> int`

- [ ] **Step 1: `ml/pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"

[project]
name = "mltools"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["numpy>=1.26", "opencv-python-headless>=4.9"]

[project.optional-dependencies]
bench = ["onnxruntime>=1.18"]
dev = ["pytest>=8", "ruff>=0.6", "bandit>=1.7"]

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
```

Crear `src/mltools/__init__.py` vacío. En `.gitignore`, reemplazar la línea `ml/data/raw/` por `ml/data/`. Desde `ml/`: `python -m venv .venv && source .venv/Scripts/activate && pip install -e ".[dev]"`.

- [ ] **Step 2: test que falla** (`ml/tests/test_dataset_check.py`)

```python
from pathlib import Path

from mltools.catalog import REPO, load_skus
from mltools.dataset_check import check_dataset, format_report

SKUS = {"AGUA", "COLA", "TAKIS"}


def put(root: Path, rel: str, content: bytes | None = None) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content if content is not None else rel.encode())


def test_counts_and_ok(tmp_path: Path):
    for i in range(3):
        put(tmp_path, f"AGUA/a_{i}.jpg")
    put(tmp_path, "COLA/c_1.PNG")
    put(tmp_path, "mezclas/m_1.jpeg")
    put(tmp_path, "videos/v_1.mp4")

    report = check_dataset(tmp_path, SKUS, min_per_product=2)

    assert report.counts == {"AGUA": 3, "COLA": 1, "mezclas": 1, "videos": 1}
    assert report.missing_skus == ["TAKIS"]
    assert report.low_skus == ["COLA"]
    assert report.ok is True


def test_unknown_folder_fails(tmp_path: Path):
    put(tmp_path, "Coca Cola/x.jpg")
    report = check_dataset(tmp_path, SKUS)
    assert report.unknown_folders == ["Coca Cola"]
    assert report.ok is False


def test_bad_extensions_fail(tmp_path: Path):
    put(tmp_path, "AGUA/nota.txt")
    put(tmp_path, "AGUA/clip.mp4")
    put(tmp_path, "videos/foto.jpg")
    report = check_dataset(tmp_path, SKUS)
    assert sorted(report.bad_files) == ["AGUA/clip.mp4", "AGUA/nota.txt", "videos/foto.jpg"]
    assert report.ok is False


def test_duplicates_counted_once(tmp_path: Path):
    put(tmp_path, "AGUA/a.jpg", b"misma")
    put(tmp_path, "AGUA/b.jpg", b"misma")
    report = check_dataset(tmp_path, SKUS)
    assert report.counts["AGUA"] == 1
    assert report.duplicates == [("AGUA/a.jpg", "AGUA/b.jpg")]
    assert report.ok is True


def test_system_files_ignored(tmp_path: Path):
    put(tmp_path, "AGUA/desktop.ini")
    put(tmp_path, "AGUA/Thumbs.db")
    report = check_dataset(tmp_path, SKUS)
    assert report.counts["AGUA"] == 0
    assert report.bad_files == []


def test_format_report_marks_states(tmp_path: Path):
    put(tmp_path, "AGUA/a.jpg")
    text = format_report(check_dataset(tmp_path, SKUS, min_per_product=5))
    assert "AGUA" in text and "pocas" in text
    assert "TAKIS" in text and "falta" in text


def test_load_skus_from_repo_catalog():
    skus = load_skus(REPO / "catalog" / "products.csv")
    assert skus and all(s == s.upper() for s in skus)
```

Run: `python -m pytest -q` → FAIL `ModuleNotFoundError`

- [ ] **Step 3: `ml/src/mltools/catalog.py`**

```python
import csv
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]


def load_skus(catalog_csv: Path) -> set[str]:
    with catalog_csv.open(encoding="utf-8", newline="") as f:
        return {row["sku"] for row in csv.DictReader(f)}
```

- [ ] **Step 4: `ml/src/mltools/dataset_check.py`**

```python
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
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
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
```

- [ ] **Step 5: verificar y hacer commit** (rama corta `feature/m1a-dataset-check`)

Run: `python -m pytest -q` → 7 passed. `ruff check .` y `bandit -r src -q` limpios.

```bash
git add ml .gitignore
git commit -m "feat(ml): verificador del dataset contra el catálogo"
```

---

### Task 2: extractor de cuadros de video

**Files:**
- Create: `ml/src/mltools/frames.py`
- Test: `ml/tests/test_frames.py`

**Interfaces:**
- Produce: `extract_frames(video: Path, out_dir: Path, every_s: float = 0.5, min_diff: float = 12.0, prefix: str | None = None) -> int` (devuelve cuántos cuadros guardó; lanza `ValueError` si no puede abrir el video) y `main(argv) -> int`

- [ ] **Step 1: test que falla** (`ml/tests/test_frames.py`)

```python
from pathlib import Path

import cv2
import numpy as np
import pytest

from mltools.frames import extract_frames

FPS = 10


def make_video(path: Path, colors: list[int], frames_each: int = 20) -> Path:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), FPS, (64, 64))
    for value in colors:
        for _ in range(frames_each):
            writer.write(np.full((64, 64, 3), value, dtype=np.uint8))
    writer.release()
    return path


def test_keeps_only_changes(tmp_path: Path):
    video = make_video(tmp_path / "v.avi", [0, 255, 0])
    saved = extract_frames(video, tmp_path / "out", every_s=0.5)
    assert saved == 3
    assert sorted(p.name for p in (tmp_path / "out").iterdir()) == [
        "v_0000.jpg",
        "v_0001.jpg",
        "v_0002.jpg",
    ]


def test_min_diff_zero_keeps_every_sample(tmp_path: Path):
    video = make_video(tmp_path / "v.avi", [0, 255, 0])
    assert extract_frames(video, tmp_path / "out", every_s=0.5, min_diff=0.0) == 12


def test_custom_prefix(tmp_path: Path):
    video = make_video(tmp_path / "v.avi", [0])
    extract_frames(video, tmp_path / "out", prefix="JP_cola")
    assert (tmp_path / "out" / "JP_cola_0000.jpg").exists()


def test_unreadable_video_raises(tmp_path: Path):
    with pytest.raises(ValueError, match="No se pudo abrir"):
        extract_frames(tmp_path / "no-existe.mp4", tmp_path / "out")
```

Run: `python -m pytest tests/test_frames.py -v` → FAIL `ModuleNotFoundError`

- [ ] **Step 2: `ml/src/mltools/frames.py`**

```python
"""Saca fotos de un video, saltando cuadros casi iguales al último guardado."""

import argparse
from pathlib import Path

import cv2
import numpy as np


def _signature(frame: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return cv2.resize(gray, (64, 64), interpolation=cv2.INTER_AREA).astype(np.float32)


def extract_frames(
    video: Path,
    out_dir: Path,
    every_s: float = 0.5,
    min_diff: float = 12.0,
    prefix: str | None = None,
) -> int:
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise ValueError(f"No se pudo abrir el video: {video}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    step = max(1, round(fps * every_s))
    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = prefix or video.stem
    last: np.ndarray | None = None
    saved = 0
    index = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if index % step == 0:
                signature = _signature(frame)
                if last is None or float(np.mean(np.abs(signature - last))) >= min_diff:
                    cv2.imwrite(str(out_dir / f"{prefix}_{saved:04d}.jpg"), frame)
                    last = signature
                    saved += 1
            index += 1
    finally:
        cap.release()
    return saved


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extrae fotos de videos del dataset.")
    parser.add_argument("videos", type=Path, nargs="+")
    parser.add_argument("--out", type=Path, required=True, help="Carpeta del producto destino")
    parser.add_argument("--every", type=float, default=0.5, help="Segundos entre muestras")
    parser.add_argument("--min-diff", type=float, default=12.0, help="Diferencia mínima (0-255)")
    args = parser.parse_args(argv)
    total = 0
    for video in args.videos:
        saved = extract_frames(video, args.out, args.every, args.min_diff)
        print(f"{video.name}: {saved} fotos")
        total += saved
    print(f"Total: {total} fotos en {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: verificar y hacer commit** (rama corta `feature/m1a-frames`)

Run: `python -m pytest -q` → 11 passed · ruff · bandit limpios.

```bash
git add ml/src/mltools/frames.py ml/tests/test_frames.py
git commit -m "feat(ml): extractor de cuadros de video sin repetidos"
```

---

### Task 3: configuración de Label Studio y guía de etiquetado

**Files:**
- Create: `ml/src/mltools/labelstudio.py`, `docs/ml/etiquetado.md`
- Test: `ml/tests/test_labelstudio.py`

**Interfaces:**
- Consume: `load_skus`, `REPO` (Task 1)
- Produce: `label_config(skus: set[str] | list[str]) -> str` (XML válido para Label Studio, con una etiqueta por SKU en orden alfabético) y `main(argv) -> int` (lo imprime, o lo escribe con `--out`)

- [ ] **Step 1: test que falla** (`ml/tests/test_labelstudio.py`)

```python
import xml.etree.ElementTree as ET

from mltools.labelstudio import label_config


def test_one_label_per_sku_sorted():
    root = ET.fromstring(label_config({"TAKIS", "AGUA", "COLA"}))
    labels = [el.get("value") for el in root.iter("Label")]
    assert labels == ["AGUA", "COLA", "TAKIS"]


def test_rectangle_labels_point_to_image():
    root = ET.fromstring(label_config(["AGUA"]))
    rect = root.find("RectangleLabels")
    image = root.find("Image")
    assert rect.get("toName") == image.get("name") == "image"
    assert image.get("value") == "$image"


def test_values_are_escaped():
    root = ET.fromstring(label_config(['RARO"<&>']))
    assert [el.get("value") for el in root.iter("Label")] == ['RARO"<&>']
```

Run: `python -m pytest tests/test_labelstudio.py -v` → FAIL `ModuleNotFoundError`

- [ ] **Step 2: `ml/src/mltools/labelstudio.py`**

```python
"""Genera la configuración de etiquetado de Label Studio a partir del catálogo."""

import argparse
from collections.abc import Iterable
from pathlib import Path
from xml.sax.saxutils import quoteattr

from mltools.catalog import REPO, load_skus


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
```

- [ ] **Step 3: `docs/ml/etiquetado.md`**

````markdown
# Guía de etiquetado (Label Studio)

Etiquetar significa dibujar un recuadro alrededor de cada producto en cada foto y decir cuál es. El modelo aprende de esos recuadros, así que **la calidad del etiquetado es la calidad del reconocedor**.

## 1. Preparar (una vez)

```bash
# Un entorno aparte para Label Studio
python -m venv ~/label-studio-env && source ~/label-studio-env/Scripts/activate   # Linux/Mac: bin/activate
pip install label-studio
label-studio start        # abre http://localhost:8080 y pide crear un usuario local
```

## 2. Revisar el dataset antes de etiquetar

Descarga la carpeta del Drive **AutoCaja-dataset** dentro de `ml/data/raw/` y ejecuta desde `ml/`:

```bash
python -m mltools.dataset_check          # corrige lo que marque ❌ antes de seguir
python -m mltools.frames ml/data/raw/videos/JP_cocacola.mp4 --out ml/data/raw/COCACOLA-500
```

## 3. Crear el proyecto

1. En Label Studio: **Create Project** → nombre `AutoCaja`.
2. **Labeling Setup → Custom template → Code**: pega lo que imprime `python -m mltools.labelstudio`. Sale una etiqueta por producto del catálogo.
3. **Data Import**: arrastra las fotos de las carpetas, de a una o dos carpetas por vez.

## 4. Reglas para dibujar

- ✅ **Un recuadro por producto**, ajustado a sus bordes, sin dejar mucho espacio.
- ✅ Si hay 3 productos, van **3 recuadros**, cada uno con su etiqueta.
- ✅ Producto cortado por el borde de la foto: se etiqueta si se ve **más de la mitad**.
- ✅ Productos que se tapan: cada uno lleva su propio recuadro, aunque se superpongan.
- ❌ No etiquetes reflejos, sombras ni productos que no están en el catálogo.
- ❌ Si una foto está borrosa o sale una persona: **Skip** y avisa para borrarla.

## 5. Exportar

Cuando todo esté etiquetado: **Export → YOLO** y descomprime el resultado en `ml/data/labeled/`. Esa carpeta, igual que `ml/data/raw/`, está fuera de git.

## Reparto sugerido

Cada persona etiqueta las fotos que **no** tomó. Así un segundo par de ojos revisa cada foto.
````

- [ ] **Step 4: verificar y hacer commit** (rama corta `feature/m1a-labelstudio`)

Run: `python -m pytest -q` → 14 passed · ruff · bandit limpios. También `python -m mltools.labelstudio` imprime el XML con los SKUs del catálogo.

```bash
git add ml/src/mltools/labelstudio.py ml/tests/test_labelstudio.py docs/ml/etiquetado.md
git commit -m "feat(ml): configuración de Label Studio desde el catálogo y guía de etiquetado"
```

---

### Task 4: benchmark de latencia (RNF-01), CI y README

**Files:**
- Create: `ml/src/mltools/bench.py`
- Modify: `.github/workflows/ci.yml`, `README.md`
- Test: `ml/tests/test_bench.py`

**Interfaces:**
- Produce: `TARGET_MS = 150.0`, `Stats(mean_ms, p50_ms, p95_ms)` con `.passes` (p95 ≤ TARGET_MS), `measure(fn, runs=50, warmup=5, clock=time.perf_counter) -> Stats`, `letterbox(image: np.ndarray, size: int = 640) -> np.ndarray` (forma `(1,3,size,size)`, float32 en [0,1]) y `main(argv) -> int` (código 0 si cumple el RNF-01, 1 si no)

- [ ] **Step 1: test que falla** (`ml/tests/test_bench.py`)

```python
import numpy as np

from mltools.bench import letterbox, measure


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def timed(clock: FakeClock, durations: list[float]):
    it = iter(durations)

    def fn() -> None:
        clock.t += next(it)

    return fn


def test_measure_stats_and_pass():
    clock = FakeClock()
    durations = [0.010] * 19 + [0.200]
    stats = measure(timed(clock, durations), runs=20, warmup=0, clock=clock)
    assert stats.p50_ms == 10.0
    assert stats.p95_ms == 10.0
    assert stats.mean_ms == 19.5
    assert stats.passes is True


def test_measure_fails_target():
    clock = FakeClock()
    stats = measure(timed(clock, [0.2] * 10), runs=10, warmup=0, clock=clock)
    assert stats.p95_ms == 200.0
    assert stats.passes is False


def test_warmup_runs_are_not_measured():
    clock = FakeClock()
    calls = []

    def fn() -> None:
        calls.append(1)
        clock.t += 1.0 if len(calls) <= 2 else 0.005

    stats = measure(fn, runs=5, warmup=2, clock=clock)
    assert len(calls) == 7
    assert stats.p95_ms == 5.0


def test_letterbox_shape_and_padding():
    image = np.zeros((720, 1280, 3), dtype=np.uint8)
    out = letterbox(image, 640)
    assert out.shape == (1, 3, 640, 640)
    assert out.dtype == np.float32
    assert abs(float(out[0, 0, 0, 320]) - 114 / 255) < 1e-6
    assert float(out[0, 0, 320, 320]) == 0.0
```

Run: `python -m pytest tests/test_bench.py -v` → FAIL `ModuleNotFoundError`

- [ ] **Step 2: `ml/src/mltools/bench.py`**

```python
"""Mide la latencia de inferencia (preprocesado + modelo ONNX) contra el RNF-01."""

import argparse
import statistics
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

TARGET_MS = 150.0


@dataclass(frozen=True)
class Stats:
    mean_ms: float
    p50_ms: float
    p95_ms: float

    @property
    def passes(self) -> bool:
        return self.p95_ms <= TARGET_MS


def measure(
    fn: Callable[[], object],
    runs: int = 50,
    warmup: int = 5,
    clock: Callable[[], float] = time.perf_counter,
) -> Stats:
    for _ in range(warmup):
        fn()
    samples = []
    for _ in range(runs):
        start = clock()
        fn()
        samples.append((clock() - start) * 1000)
    samples.sort()
    p95 = samples[min(len(samples) - 1, round(0.95 * (len(samples) - 1)))]
    return Stats(
        round(statistics.fmean(samples), 1),
        round(statistics.median(samples), 1),
        round(p95, 1),
    )


def letterbox(image: np.ndarray, size: int = 640) -> np.ndarray:
    h, w = image.shape[:2]
    scale = min(size / h, size / w)
    nh, nw = round(h * scale), round(w * scale)
    resized = cv2.resize(image, (nw, nh), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((size, size, 3), 114, dtype=np.uint8)
    top, left = (size - nh) // 2, (size - nw) // 2
    canvas[top : top + nh, left : left + nw] = resized
    rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
    return rgb.transpose(2, 0, 1)[None].astype(np.float32) / 255.0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Benchmark de latencia del modelo (RNF-01).")
    parser.add_argument("--model", type=Path, required=True, help="Modelo .onnx")
    parser.add_argument("--image", type=Path, help="Foto de prueba (si no, una imagen sintética)")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--runs", type=int, default=50)
    args = parser.parse_args(argv)

    import onnxruntime as ort  # opcional: pip install -e ".[bench]"

    session = ort.InferenceSession(str(args.model), providers=["CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name
    if args.image:
        image = cv2.imread(str(args.image))
        if image is None:
            print(f"No se pudo leer la imagen {args.image}")
            return 1
    else:
        image = np.random.default_rng(0).integers(0, 255, (720, 1280, 3), dtype=np.uint8)

    stats = measure(lambda: session.run(None, {input_name: letterbox(image, args.imgsz)}), args.runs)
    verdict = "CUMPLE" if stats.passes else "NO CUMPLE"
    print(f"Modelo: {args.model.name} · imgsz {args.imgsz} · {args.runs} corridas")
    print(f"Media {stats.mean_ms} ms · p50 {stats.p50_ms} ms · p95 {stats.p95_ms} ms")
    print(f"RNF-01 (p95 ≤ {TARGET_MS:.0f} ms): {verdict}")
    return 0 if stats.passes else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

Nota sobre el test: con 20 muestras, `round(0.95 * 19) = 18` (índice 18 de la lista ordenada), es decir, el valor 10 ms.

- [ ] **Step 3: job `ml` en `.github/workflows/ci.yml`** (al mismo nivel que `kiosk-api`)

```yaml
  ml:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: ml
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e ".[dev]"
      - run: ruff check .
      - run: bandit -r src -q
      - run: python -m pytest -q
```

- [ ] **Step 4: README**: añadir al final

````markdown
## Herramientas del dataset (`ml/`)

```bash
cd ml
python -m venv .venv && source .venv/Scripts/activate
pip install -e ".[dev,bench]"

python -m mltools.dataset_check                 # revisa ml/data/raw/ contra el catálogo
python -m mltools.frames VIDEO.mp4 --out ml/data/raw/SKU   # fotos desde un video
python -m mltools.labelstudio                   # configuración para Label Studio
python -m mltools.bench --model modelo.onnx     # latencia vs RNF-01 (p95 ≤ 150 ms)
```

Guía de etiquetado: [`docs/ml/etiquetado.md`](docs/ml/etiquetado.md). Los datos (`ml/data/`) nunca van a git.
````

- [ ] **Step 5: verificar y hacer commit** (rama corta `feature/m1a-bench`)

Run: `python -m pytest -q` → 18 passed · ruff · bandit limpios.

```bash
git add ml/src/mltools/bench.py ml/tests/test_bench.py .github/workflows/ci.yml README.md
git commit -m "feat(ml): benchmark de latencia RNF-01; ci: job ml; docs: herramientas del dataset"
```

---

## Cobertura

| Necesidad | Tarea |
|---|---|
| Revisar el Drive contra el catálogo (nombres, cantidades, repetidas, formatos) | 1 |
| Aprovechar los videos sin cuadros repetidos | 2 |
| Etiquetado coherente con los SKUs y guía para el equipo | 3 |
| Medir el riesgo del RNF-01 antes de entrenar | 4 (después de la ejecución, el controlador lo mide con YOLOv8n preentrenado, previo permiso de descarga) |
