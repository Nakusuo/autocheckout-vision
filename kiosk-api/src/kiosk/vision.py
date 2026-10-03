"""Reconocimiento con YOLOv8 exportado a ONNX (requiere el extra `vision`)."""

from dataclasses import dataclass

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
