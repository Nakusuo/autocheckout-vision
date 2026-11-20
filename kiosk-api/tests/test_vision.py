from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from kiosk.tray import Detector
from kiosk.vision import (
    CameraSource,
    ImageFolderSource,
    YoloOnnxDetector,
    class_names_from_metadata,
    decode_yolov8,
    letterbox,
)


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


def test_class_names_from_ultralytics_metadata():
    assert class_names_from_metadata({"names": "{0: 'AGUA', 1: 'COLA'}"}) == ["AGUA", "COLA"]


def test_class_names_missing_raises():
    with pytest.raises(ValueError, match="names"):
        class_names_from_metadata({})


def test_image_folder_source_cycles(tmp_path: Path):
    for i, value in enumerate([0, 255]):
        cv2.imwrite(str(tmp_path / f"{i}.png"), np.full((8, 8, 3), value, dtype=np.uint8))
    source = ImageFolderSource.from_folder(tmp_path)
    firsts = [int(source.read()[0, 0, 0]) for _ in range(3)]
    assert firsts == [0, 255, 0]


def test_image_folder_source_empty_raises(tmp_path: Path):
    with pytest.raises(ValueError):
        ImageFolderSource.from_folder(tmp_path)


class FakeSession:
    def __init__(self, output: np.ndarray):
        self.output = output
        self.shapes: list[tuple] = []

    def get_inputs(self):
        return [SimpleNamespace(name="images")]

    def run(self, _outputs, feed):
        self.shapes.append(feed["images"].shape)
        return [self.output]


def test_detector_maps_classes_to_skus():
    out = yolo_output(
        [
            [100, 100, 50, 50, 0.9, 0.0, 0.0],
            [300, 300, 40, 40, 0.0, 0.0, 0.7],
        ]
    )
    session = FakeSession(out)
    source = ImageFolderSource([np.zeros((480, 640, 3), dtype=np.uint8)])
    detector = YoloOnnxDetector(session, ["AGUA", "COLA", "TAKIS"], source)

    assert detector.detect() == ["AGUA", "TAKIS"]
    assert session.shapes == [(1, 3, 416, 416)]
    assert isinstance(detector, Detector)


def test_camera_can_be_closed_and_explicitly_reopened(monkeypatch):
    image = np.zeros((8, 8, 3), dtype=np.uint8)

    class Capture:
        def __init__(self, index):
            self.active = True

        def isOpened(self):
            return self.active

        def read(self):
            return self.active, image

        def release(self):
            self.active = False

    monkeypatch.setattr(cv2, "VideoCapture", Capture)
    source = CameraSource(0)
    assert source.read().shape == (8, 8, 3)
    source.close()
    source.close()
    with pytest.raises(OSError):
        source.read()
    assert callable(getattr(source, "open", None))
    source.open()
    assert source.read().shape == (8, 8, 3)
    source.close()
