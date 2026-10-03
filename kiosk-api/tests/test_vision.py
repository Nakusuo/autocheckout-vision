import numpy as np

from kiosk.vision import decode_yolov8, letterbox


def yolo_output(rows: list[list[float]]) -> np.ndarray:
    """rows: [cx, cy, w, h, s0, s1, s2] por anchor → forma (1, 7, N) como YOLOv8."""
    return np.array(rows, dtype=np.float32).T[None]


def test_decode_keeps_best_and_suppresses_duplicates():
    out = yolo_output(
        [
            [100, 100, 50, 50, 0.9, 0.0, 0.0],
            [102, 101, 50, 50, 0.8, 0.0, 0.0],
            [300, 300, 40, 40, 0.0, 0.0, 0.7],
            [200, 50, 30, 30, 0.3, 0.0, 0.0],
        ]
    )
    dets = decode_yolov8(out, conf=0.5, iou=0.45)
    assert [(d.class_id, round(d.score, 2)) for d in dets] == [(0, 0.9), (2, 0.7)]
    assert dets[0].box == (75.0, 75.0, 50.0, 50.0)


def test_decode_nothing_above_confidence():
    out = yolo_output([[100, 100, 50, 50, 0.2, 0.1, 0.0]])
    assert decode_yolov8(out, conf=0.5) == []


def test_decode_is_class_agnostic():
    out = yolo_output(
        [
            [100, 100, 50, 50, 0.9, 0.0, 0.0],
            [100, 100, 50, 50, 0.0, 0.85, 0.0],
        ]
    )
    assert [d.class_id for d in decode_yolov8(out)] == [0]


def test_letterbox_shape_and_padding():
    out = letterbox(np.zeros((480, 640, 3), dtype=np.uint8), 416)
    assert out.shape == (1, 3, 416, 416)
    assert out.dtype == np.float32
    assert abs(float(out[0, 0, 0, 208]) - 114 / 255) < 1e-6
    assert float(out[0, 0, 208, 208]) == 0.0
