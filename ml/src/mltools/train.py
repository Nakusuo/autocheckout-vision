"""Entrena YOLOv8n con el dataset del equipo, lo evalúa en test y lo exporta a ONNX.

Requiere el extra `train` (ultralytics). Ver docs/ml/entrenamiento.md.
"""

import argparse
import json
import shutil
from pathlib import Path

from mltools.catalog import REPO
from mltools.console import utf8_output

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
    utf8_output()
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
