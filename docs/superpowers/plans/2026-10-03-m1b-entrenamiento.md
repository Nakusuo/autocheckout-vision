# M1 parte B — Dataset y entrenamiento: plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Objetivo:** pasar de la exportación de Label Studio a un modelo `autocaja-416.onnx` evaluado contra la meta, con dos comandos: `python -m mltools.split` y `python -m mltools.train`.

**Arquitectura:** `mltools.split` valida la exportación YOLO de Label Studio (clases contra el catálogo, cada foto con su etiqueta, líneas bien formadas), la reparte de forma determinista en 70/20/10 y escribe `data.yaml`. `mltools.train` entrena YOLOv8n a 416 px con aumentos pensados para la vista cenital, evalúa en `test` y exporta a ONNX con un JSON de resultados. Ultralytics va en el extra `train` y se importa de forma diferida: la CI no lo instala.

**Stack:** Python 3.12, ultralytics (AGPL-3.0, igual que el repo), pytest.

**Spec:** [`docs/superpowers/specs/2026-10-03-autocheckout-design.md`](../specs/2026-10-03-autocheckout-design.md) · Benchmark: [`docs/ml/benchmark.md`](../../ml/benchmark.md)

## Restricciones globales

- Reparto **70/20/10** (train/val/test), determinista con `seed` (42 por defecto), ordenado por `sha256(f"{seed}:{nombre}")`.
- Las clases de `classes.txt` deben existir en `catalog/products.csv`, y su **orden se respeta** como ids de `data.yaml`.
- Cada foto lleva su `.txt`. Cada línea tiene la forma `clase cx cy w h`, con `0 ≤ clase < nº clases` y las coordenadas en [0, 1]. Un `.txt` vacío vale (foto sin productos).
- `split` **solo borra** la carpeta de salida si contiene un `data.yaml` (es decir, la generó él). Si la carpeta existe con otra cosa dentro, se detiene con un error.
- Entrenamiento: `imgsz` **416**, base `yolov8n.pt`, aumentos `degrees=180` y `fliplr=0`/`flipud=0` (en la vista cenital los productos aparecen girados, nunca espejados).
- Meta: **mAP50 ≥ 0,90 en test**. Si no se cumple, el comando sale con código 1.
- Salidas en `ml/data/models/`: `autocaja-416.onnx` y `autocaja-416.json`. Todo `ml/data/` está fuera de git.
- Ramas cortas por tarea, unidas con `--no-ff` a `feature/m1-entrenamiento`, sin Co-Authored-By.

---

### Task 1: armar el dataset desde Label Studio

**Files:**
- Create: `ml/src/mltools/split.py`
- Test: `ml/tests/test_split.py`

**Interfaces:**
- Consume: `REPO`, `load_skus` (`mltools.catalog`)
- Produce: `split_names(names: list[str], ratios=(0.7, 0.2, 0.1), seed: int = 42) -> dict[str, list[str]]`, `read_classes(export_dir: Path) -> list[str]`, `build_dataset(export_dir: Path, out_dir: Path, skus: set[str], seed: int = 42) -> Path` (devuelve la ruta de `data.yaml`; lanza `ValueError` con el mensaje en español) y `main(argv) -> int`

- [ ] **Step 1: test que falla** (`ml/tests/test_split.py`)

```python
from pathlib import Path

import pytest

from mltools.split import build_dataset, split_names

SKUS = {"AGUA", "COLA", "TAKIS"}


def make_export(root: Path, n: int = 10, classes=("AGUA", "COLA"), label="0 0.5 0.5 0.2 0.2") -> Path:
    (root / "images").mkdir(parents=True)
    (root / "labels").mkdir()
    (root / "classes.txt").write_text("\n".join(classes) + "\n", encoding="utf-8")
    for i in range(n):
        (root / "images" / f"foto_{i:02d}.jpg").write_bytes(b"jpg")
        (root / "labels" / f"foto_{i:02d}.txt").write_text(label + "\n", encoding="utf-8")
    return root


def test_split_names_is_deterministic_70_20_10():
    names = [f"f{i}" for i in range(10)]
    a = split_names(names, seed=7)
    assert a == split_names(list(reversed(names)), seed=7)
    assert [len(a[k]) for k in ("train", "val", "test")] == [7, 2, 1]
    assert sorted(a["train"] + a["val"] + a["test"]) == sorted(names)


def test_build_dataset_writes_splits_and_yaml(tmp_path: Path):
    export = make_export(tmp_path / "export")
    yaml = build_dataset(export, tmp_path / "dataset", SKUS)

    text = yaml.read_text(encoding="utf-8")
    assert "train: images/train" in text and "test: images/test" in text
    assert "  0: AGUA" in text and "  1: COLA" in text
    counts = [len(list((tmp_path / "dataset" / "images" / s).iterdir())) for s in ("train", "val", "test")]
    assert counts == [7, 2, 1]
    assert len(list((tmp_path / "dataset" / "labels" / "train").iterdir())) == 7


def test_unknown_class_is_rejected(tmp_path: Path):
    export = make_export(tmp_path / "export", classes=("AGUA", "PEPSI"))
    with pytest.raises(ValueError, match="catálogo"):
        build_dataset(export, tmp_path / "dataset", SKUS)


def test_missing_label_is_rejected(tmp_path: Path):
    export = make_export(tmp_path / "export")
    (export / "labels" / "foto_03.txt").unlink()
    with pytest.raises(ValueError, match="sin etiquetas"):
        build_dataset(export, tmp_path / "dataset", SKUS)


@pytest.mark.parametrize("label", ["5 0.5 0.5 0.2 0.2", "0 0.5 0.5 1.2 0.2", "0 0.5 0.5"])
def test_bad_label_lines_are_rejected(tmp_path: Path, label: str):
    export = make_export(tmp_path / "export", label=label)
    with pytest.raises(ValueError, match="etiqueta inválida"):
        build_dataset(export, tmp_path / "dataset", SKUS)


def test_output_folder_is_protected(tmp_path: Path):
    export = make_export(tmp_path / "export")
    out = tmp_path / "dataset"
    out.mkdir()
    (out / "importante.txt").write_text("no borrar", encoding="utf-8")
    with pytest.raises(ValueError, match="no fue generada"):
        build_dataset(export, out, SKUS)
    assert (out / "importante.txt").exists()

    (out / "importante.txt").unlink()
    build_dataset(export, out, SKUS)
    build_dataset(export, out, SKUS)  # una segunda vez la reemplaza sin error
    assert (out / "data.yaml").exists()
```

Run: `python -m pytest tests/test_split.py -v` → FAIL `ModuleNotFoundError`

- [ ] **Step 2: `ml/src/mltools/split.py`**

```python
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
```

- [ ] **Step 3: verificar y hacer commit** (rama corta `feature/m1b-split`)

Run: `python -m pytest -q` → 26 passed (18 + 8). ruff y bandit limpios.

```bash
git add ml/src/mltools/split.py ml/tests/test_split.py
git commit -m "feat(ml): arma el dataset 70/20/10 desde la exportación de Label Studio"
```

---

### Task 2: entrenamiento, evaluación y exportación

**Files:**
- Modify: `ml/pyproject.toml` (extra `train`)
- Create: `ml/src/mltools/train.py`, `docs/ml/entrenamiento.md`
- Modify: `README.md` (dos líneas en la sección de `ml/`)
- Test: `ml/tests/test_train.py`

**Interfaces:**
- Produce: `MAP50_TARGET = 0.90`, `IMGSZ = 416`, `AUGMENT: dict`, `evaluate_gate(map50: float, target: float = MAP50_TARGET) -> tuple[bool, str]`, `train_and_export(data_yaml: Path, out_dir: Path, epochs: int = 100, imgsz: int = IMGSZ, base: str | None = None, seed: int = 42) -> dict` y `main(argv) -> int`

- [ ] **Step 1:** en `ml/pyproject.toml`, dentro de `[project.optional-dependencies]`, añadir `train = ["ultralytics>=8.3"]`. **No** lo instales en el venv de `ml/` (pesa más de 1 GB). La CI tampoco lo instala.

- [ ] **Step 2: test que falla** (`ml/tests/test_train.py`)

```python
from pathlib import Path

from mltools.train import AUGMENT, evaluate_gate, main


def test_gate_passes_above_target():
    ok, message = evaluate_gate(0.934)
    assert ok is True
    assert "0.934" in message and "CUMPLE" in message


def test_gate_exact_target_passes():
    assert evaluate_gate(0.90)[0] is True


def test_gate_fails_below_target():
    ok, message = evaluate_gate(0.81)
    assert ok is False and "NO CUMPLE" in message


def test_overhead_augmentations_rotate_but_never_mirror():
    assert AUGMENT["degrees"] == 180.0
    assert AUGMENT["fliplr"] == 0.0 and AUGMENT["flipud"] == 0.0


def test_main_without_dataset_returns_1(tmp_path: Path, capsys):
    assert main(["--data", str(tmp_path / "no-existe.yaml")]) == 1
    assert "mltools.split" in capsys.readouterr().out
```

Run: `python -m pytest tests/test_train.py -v` → FAIL `ModuleNotFoundError`

- [ ] **Step 3: `ml/src/mltools/train.py`**

```python
"""Entrena YOLOv8n con el dataset del equipo, lo evalúa en test y lo exporta a ONNX.

Requiere el extra `train` (ultralytics). Ver docs/ml/entrenamiento.md.
"""

import argparse
import json
import shutil
from pathlib import Path

from mltools.catalog import REPO

MAP50_TARGET = 0.90
IMGSZ = 416
# Vista cenital: los productos aparecen en cualquier giro, pero nunca espejados
# (el texto de las etiquetas jamás se ve al revés en la bandeja).
AUGMENT = {"degrees": 180.0, "fliplr": 0.0, "flipud": 0.0}
MODELS_DIR = REPO / "ml" / "data" / "models"


def evaluate_gate(map50: float, target: float = MAP50_TARGET) -> tuple[bool, str]:
    ok = map50 >= target
    verdict = "CUMPLE" if ok else "NO CUMPLE"
    return ok, f"mAP50 en test: {map50:.3f} (meta ≥ {target:.2f}): {verdict}"


def train_and_export(
    data_yaml: Path,
    out_dir: Path,
    epochs: int = 100,
    imgsz: int = IMGSZ,
    base: str | None = None,
    seed: int = 42,
) -> dict:
    from ultralytics import YOLO

    local_base = MODELS_DIR / "yolov8n.pt"
    model = YOLO(base or (str(local_base) if local_base.exists() else "yolov8n.pt"))
    model.train(
        data=str(data_yaml),
        epochs=epochs,
        imgsz=imgsz,
        seed=seed,
        project=str(out_dir / "runs"),
        name="autocaja",
        exist_ok=True,
        **AUGMENT,
    )
    best = YOLO(str(model.trainer.best))
    metrics = best.val(data=str(data_yaml), split="test", imgsz=imgsz)
    map50 = float(metrics.box.map50)
    exported = Path(best.export(format="onnx", imgsz=imgsz))
    final = out_dir / f"autocaja-{imgsz}.onnx"
    shutil.copy2(exported, final)
    result = {"map50_test": round(map50, 4), "imgsz": imgsz, "epochs": epochs, "model": final.name}
    (out_dir / f"autocaja-{imgsz}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Entrena y exporta el reconocedor de productos.")
    parser.add_argument("--data", type=Path, default=REPO / "ml" / "data" / "dataset" / "data.yaml")
    parser.add_argument("--out", type=Path, default=MODELS_DIR)
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--imgsz", type=int, default=IMGSZ)
    args = parser.parse_args(argv)
    if not args.data.exists():
        print(f"No existe {args.data}. Ejecuta primero: python -m mltools.split")
        return 1
    args.out.mkdir(parents=True, exist_ok=True)
    result = train_and_export(args.data, args.out, args.epochs, args.imgsz)
    ok, message = evaluate_gate(result["map50_test"])
    model_path = args.out / result["model"]
    print(message)
    print(f"Modelo: {model_path}")
    print(f"Mide la latencia: python -m mltools.bench --model {model_path} --imgsz {args.imgsz}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: `docs/ml/entrenamiento.md`**

````markdown
# Entrenamiento del reconocedor

Requisito previo: fotos etiquetadas y exportadas desde Label Studio (ver [etiquetado.md](etiquetado.md)).

## 1. Exportación → dataset

Descomprime la exportación **YOLO** de Label Studio en `ml/data/labeled/`. Tiene que quedar así:

```
ml/data/labeled/
  classes.txt
  images/   (fotos)
  labels/   (un .txt por foto)
```

Desde `ml/` (venv del proyecto):

```bash
python -m mltools.split        # valida y reparte 70/20/10 en data/dataset/ + data.yaml
```

Si marca ❌, corrige en Label Studio y vuelve a exportar.

## 2. Entrenar (CPU)

El entrenamiento usa Ultralytics (AGPL-3.0), que pesa más de 1 GB. Va en un entorno aparte, con una ruta corta por el límite de rutas largas de Windows:

```bash
python -m venv ~/.venvs/yolo && source ~/.venvs/yolo/Scripts/activate
pip install --index-url https://download.pytorch.org/whl/cpu torch torchvision
pip install -e "ml[train]"          # desde la raíz del repo

cd ml
python -m mltools.train --epochs 100
```

Al terminar deja `data/models/autocaja-416.onnx` y `autocaja-416.json`, e imprime:

- `mAP50 en test … CUMPLE / NO CUMPLE` (meta ≥ 0,90).
- El comando para medir la latencia (RNF-01).

En CPU, con unas 800 fotos, puede tardar **varias horas**. Para probar el flujo rápido usa `--epochs 5`.

### Alternativa con GPU gratuita

Google Colab: sube `data/dataset/` y ejecuta los mismos comandos. Ten en cuenta que las fotos quedan en servidores de Google.

## 3. Si no cumple la meta

1. Revisa en `data/models/runs/autocaja/` las matrices de confusión: ¿qué productos se confunden?
2. Más fotos de esos productos, sobre todo en `mezclas`.
3. Probar con `--imgsz 480` (y volver a medir la latencia).

## 4. Usarlo en el quiosco

```bash
export KIOSK_MODE=camera
export KIOSK_MODEL=../ml/data/models/autocaja-416.onnx
python -m kiosk
```
````

- [ ] **Step 5: README**: en la sección «Herramientas del dataset (`ml/`)», añadir dentro del bloque de comandos, después de la línea de `labelstudio`:

```bash
python -m mltools.split                         # exportación de Label Studio → dataset 70/20/10
python -m mltools.train                         # entrena, evalúa (mAP50 ≥ 0,90) y exporta a ONNX
```

y debajo de la línea de la guía de etiquetado: `Guía de entrenamiento: [`docs/ml/entrenamiento.md`](docs/ml/entrenamiento.md).`

- [ ] **Step 6: verificar y hacer commit** (rama corta `feature/m1b-train`)

Run: `python -m pytest -q` → 31 passed (26 + 5). ruff y bandit limpios.

```bash
git add ml/pyproject.toml ml/src/mltools/train.py ml/tests/test_train.py docs/ml/entrenamiento.md README.md
git commit -m "feat(ml): entrenamiento YOLOv8n a 416, evaluación contra la meta y exportación ONNX"
```

---

## Verificación de punta a punta (controlador, tras las tareas)

Generar en el scratchpad un dataset sintético (rectángulos de colores con etiquetas YOLO y 2 clases del catálogo), pasarlo por `mltools.split`, entrenar 3 épocas con `~/.venvs/yolo` y comprobar que salen `autocaja-416.onnx` y el JSON, y que `python -m kiosk.vision` / `YoloOnnxDetector.from_model` leen los nombres de clase del ONNX. El resultado no se guarda en `ml/data/models/` (se usa una carpeta temporal `--out`).
