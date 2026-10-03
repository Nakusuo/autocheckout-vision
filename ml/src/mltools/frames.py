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
    failed = False
    for video in args.videos:
        try:
            saved = extract_frames(video, args.out, args.every, args.min_diff, prefix=video.stem)
            print(f"{video.name}: {saved} fotos")
            total += saved
        except ValueError as e:
            print(f"{video.name}: {e}")
            failed = True
    print(f"Total: {total} fotos en {args.out}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
