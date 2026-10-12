"""Reconocimiento con YOLOv8 exportado a ONNX (requiere el extra `vision`)."""

import argparse
import ast
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import cv2
import numpy as np


def letterbox(image: np.ndarray, size: int = 416) -> np.ndarray:
    h, w = image.shape[:2]
    scale = min(size / h, size / w)
    nh, nw = round(h * scale), round(w * scale)
    resized = cv2.resize(image, (nw, nh), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((size, size, 3), 114, dtype=np.uint8)
    top, left = (size - nh) // 2, (size - nw) // 2
    canvas[top : top + nh, left : left + nw] = resized
    rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
    return rgb.transpose(2, 0, 1)[None].astype(np.float32) / 255.0


@dataclass(frozen=True)
class Detection:
    class_id: int
    score: float
    box: tuple[float, float, float, float]  # x, y, w, h en coordenadas de la entrada del modelo


def decode_yolov8(output: np.ndarray, conf: float = 0.5, iou: float = 0.45) -> list[Detection]:
    preds = np.asarray(output)[0].T  # (N, 4 + nc)
    if preds.size == 0:
        return []
    class_scores = preds[:, 4:]
    class_ids = class_scores.argmax(axis=1)
    scores = class_scores.max(axis=1)
    keep = scores >= conf
    preds, class_ids, scores = preds[keep], class_ids[keep], scores[keep]
    if len(scores) == 0:
        return []
    cx, cy, w, h = preds[:, 0], preds[:, 1], preds[:, 2], preds[:, 3]
    boxes = np.stack([cx - w / 2, cy - h / 2, w, h], axis=1)
    kept = cv2.dnn.NMSBoxes(boxes.tolist(), scores.tolist(), conf, iou)
    return [
        Detection(int(class_ids[i]), float(scores[i]), tuple(float(v) for v in boxes[i]))
        for i in np.array(kept).flatten()
    ]


IMAGE_EXT = {".jpg", ".jpeg", ".png"}


def class_names_from_metadata(meta: dict[str, str]) -> list[str]:
    raw = meta.get("names")
    if not raw:
        raise ValueError("El modelo no trae nombres de clases (metadata 'names')")
    parsed = ast.literal_eval(raw)
    return [str(parsed[i]) for i in sorted(parsed)]


class FrameSource(Protocol):
    def read(self) -> np.ndarray: ...


class CameraSource:
    def __init__(self, index: int = 0):
        self._cap = cv2.VideoCapture(index)
        if not self._cap.isOpened():
            raise OSError(f"No se pudo abrir la cámara {index}")

    def read(self) -> np.ndarray:
        ok, frame = self._cap.read()
        if not ok:
            raise OSError("La cámara no entregó imagen")
        return frame

    def close(self) -> None:
        self._cap.release()


class ImageFolderSource:
    """Fuente de pruebas: entrega imágenes ya cargadas, en bucle."""

    def __init__(self, images: list[np.ndarray]):
        if not images:
            raise ValueError("No hay imágenes para la fuente de pruebas")
        self._images = images
        self._next = 0

    @classmethod
    def from_folder(cls, folder: Path) -> "ImageFolderSource":
        paths = sorted(p for p in folder.iterdir() if p.suffix.lower() in IMAGE_EXT)
        images = [img for p in paths if (img := cv2.imread(str(p))) is not None]
        return cls(images)

    def read(self) -> np.ndarray:
        image = self._images[self._next % len(self._images)]
        self._next += 1
        return image


class YoloOnnxDetector:
    def __init__(
        self,
        session,
        class_names: list[str],
        source: FrameSource,
        imgsz: int = 416,
        conf: float = 0.5,
        iou: float = 0.45,
    ):
        self._session = session
        self._input = session.get_inputs()[0].name
        self._names = class_names
        self._source = source
        self._imgsz = imgsz
        self._conf = conf
        self._iou = iou

    @classmethod
    def from_model(
        cls,
        model_path: Path,
        source: FrameSource,
        imgsz: int = 416,
        conf: float = 0.5,
        iou: float = 0.45,
    ) -> "YoloOnnxDetector":
        import onnxruntime as ort

        session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
        names = class_names_from_metadata(session.get_modelmeta().custom_metadata_map)
        return cls(session, names, source, imgsz, conf, iou)

    def detect(self) -> list[str]:
        frame = self._source.read()
        output = self._session.run(None, {self._input: letterbox(frame, self._imgsz)})[0]
        return [self._names[d.class_id] for d in decode_yolov8(output, self._conf, self._iou)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prueba la webcam con un modelo YOLOv8 ONNX.")
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--imgsz", type=int, default=416)
    parser.add_argument("--frames", type=int, default=20)
    args = parser.parse_args(argv)
    try:
        source = CameraSource(args.camera)
    except OSError as e:
        print(e)
        return 1
    try:
        detector = YoloOnnxDetector.from_model(args.model, source, imgsz=args.imgsz)
        for _ in range(args.frames):
            start = time.perf_counter()
            skus = detector.detect()
            print(f"{(time.perf_counter() - start) * 1000:6.1f} ms  {skus}")
    finally:
        source.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
