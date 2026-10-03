"""Mide la latencia de inferencia (preprocesado + modelo ONNX) contra el RNF-01."""

import argparse
import statistics
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from mltools.console import utf8_output

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
    utf8_output()
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
